from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models
from app.services.payments import pay_invoice
from app.services.plan_changes import add_interval

REMINDER_DAYS = 3


def price_for(db: Session, plan: models.Plan, currency: str) -> int:
    """Price of a plan in the customer's currency."""
    currency = currency.lower()
    if currency == plan.currency.lower():
        return plan.amount_cents
    row = db.query(models.PlanPrice).filter_by(plan_id=plan.id, currency=currency).first()
    if not row:
        raise ValueError(f"Plan {plan.id} has no price in {currency.upper()}")
    return row.amount_cents


def set_price(db: Session, plan_id: int, currency: str, amount_cents: int):
    if not db.get(models.Plan, plan_id):
        raise ValueError("Plan not found")
    currency = currency.lower()
    row = db.query(models.PlanPrice).filter_by(plan_id=plan_id, currency=currency).first()
    if row:
        row.amount_cents = amount_cents
    else:
        row = models.PlanPrice(plan_id=plan_id, currency=currency, amount_cents=amount_cents)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def start_trial(db: Session, customer_id: int, plan_id: int, days: int, currency: str):
    plan = db.get(models.Plan, plan_id)
    if not plan:
        raise ValueError("Plan not found")
    if not db.get(models.Customer, customer_id):
        raise ValueError("Customer not found")
    price_for(db, plan, currency)  # fail now if there's no price in this currency

    start = datetime.utcnow()
    end = start + timedelta(days=days)
    sub = models.Subscription(
        customer_id=customer_id, plan_id=plan_id, status="trialing",
        current_period_start=start, current_period_end=end,
    )
    db.add(sub)
    db.flush()
    trial = models.Trial(subscription_id=sub.id, trial_end=end, currency=currency.lower())
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return sub, trial


def convert_trial(db: Session, trial: models.Trial, payment_method: str):
    sub = db.get(models.Subscription, trial.subscription_id)
    plan = db.get(models.Plan, sub.plan_id)
    amount = price_for(db, plan, trial.currency)

    start = datetime.utcnow()
    sub.status = "active"
    sub.current_period_start = start
    sub.current_period_end = add_interval(start, plan.interval)
    invoice = models.Invoice(
        subscription_id=sub.id, amount_cents=amount,
        currency=trial.currency, status="open",
    )
    db.add(invoice)
    trial.converted = True
    db.commit()
    db.refresh(invoice)

    # If the card fails, pay_invoice marks the invoice failed and the sub past_due,
    # and the dunning job from Step 6 takes over.
    payment = pay_invoice(db, invoice, payment_method)
    return invoice, payment


def trial_usage(db: Session, subscription_id: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.UsageEvent.quantity), 0))
        .filter(models.UsageEvent.subscription_id == subscription_id)
        .scalar()
    )
    return int(total)


def run_trials(db: Session, payment_method: str, force: bool = False) -> list[dict]:
    """Convert trials that have ended; queue reminders for those ending soon."""
    now = datetime.utcnow()
    report = []
    for t in db.query(models.Trial).filter_by(converted=False).all():
        sub = db.get(models.Subscription, t.subscription_id)
        if sub.status != "trialing":
            continue
        if force or t.trial_end <= now:
            invoice, payment = convert_trial(db, t, payment_method)
            report.append({
                "subscription_id": sub.id, "invoice_id": invoice.id,
                "result": "converted" if payment.status == "succeeded" else "payment_failed",
                "reason": payment.failure_reason,
            })
        elif t.trial_end - now <= timedelta(days=REMINDER_DAYS) and not t.reminder_sent:
            t.reminder_sent = True  # Step 11 will send the actual email here
            db.commit()
            report.append({
                "subscription_id": sub.id, "result": "reminder_queued",
                "days_left": (t.trial_end - now).days,
            })
    return report