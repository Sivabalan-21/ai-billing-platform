from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app import models, schemas
from app.services.billing import utcnow, period_end, plan_change_amount

router = APIRouter()


@router.post("/plans", response_model=schemas.PlanOut)
def create_plan(data: schemas.PlanIn, db: Session = Depends(get_db)):
    plan = models.Plan(**data.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans", response_model=list[schemas.PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.query(models.Plan).all()


@router.post("/customers", response_model=schemas.CustomerOut)
def create_customer(data: schemas.CustomerIn, db: Session = Depends(get_db)):
    if db.query(models.Customer).filter_by(email=data.email).first():
        raise HTTPException(409, "Email already registered")
    customer = models.Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/subscriptions", response_model=schemas.SubscriptionOut)
def create_subscription(data: schemas.SubscriptionIn, db: Session = Depends(get_db)):
    customer = db.get(models.Customer, data.customer_id)
    plan = db.get(models.Plan, data.plan_id)
    if not customer or not plan:
        raise HTTPException(404, "Customer or plan not found")
    if customer.currency != plan.currency:
        raise HTTPException(400, "Customer and plan currency do not match")

    now = utcnow()
    trialing = plan.trial_days > 0
    trial_end = now + timedelta(days=plan.trial_days) if trialing else None
    sub = models.Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        status="trialing" if trialing else "active",
        current_period_start=now,
        current_period_end=trial_end or period_end(now, plan.interval),
        trial_end=trial_end,
        last_active_at=now,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/subscriptions/{sub_id}/change-plan")
def change_plan(sub_id: int, data: schemas.ChangePlanIn, db: Session = Depends(get_db)):
    sub = db.get(models.Subscription, sub_id)
    new_plan = db.get(models.Plan, data.new_plan_id)
    if not sub or not new_plan:
        raise HTTPException(404, "Subscription or plan not found")
    if sub.status != "active":
        raise HTTPException(400, "Only active subscriptions can change plan")
    if new_plan.id == sub.plan_id:
        raise HTTPException(400, "Already on this plan")
    if new_plan.currency != sub.plan.currency:
        raise HTTPException(400, "Cannot switch between currencies")

    now = utcnow()
    net, new_period = plan_change_amount(sub, sub.plan, new_plan, now)

    sub.plan_id = new_plan.id
    if new_period:
        sub.current_period_start = now
        sub.current_period_end = period_end(now, new_plan.interval)

    invoice_id = None
    if net > 0:
        invoice = models.Invoice(
            subscription_id=sub.id,
            amount_cents=net,
            currency=new_plan.currency,
            status="open",
            due_date=now,
        )
        db.add(invoice)
        db.flush()
        invoice_id = invoice.id

    db.commit()
    return {
        "subscription_id": sub.id,
        "new_plan": new_plan.name,
        "amount_due_cents": max(net, 0),
        "credit_cents": max(-net, 0),
        "invoice_id": invoice_id,
    }


@router.post("/subscriptions/{sub_id}/cancel", response_model=schemas.SubscriptionOut)
def cancel_subscription(sub_id: int, db: Session = Depends(get_db)):
    sub = db.get(models.Subscription, sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    sub.status = "canceled"
    sub.canceled_at = utcnow()
    db.commit()
    db.refresh(sub)
    return sub