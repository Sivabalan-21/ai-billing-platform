from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app import models, schemas
from app.services.billing import utcnow, period_end

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
