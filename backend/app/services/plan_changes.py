import calendar
from datetime import datetime
from sqlalchemy.orm import Session
from app import models


def _naive(dt):
    return dt.replace(tzinfo=None) if dt else None


def add_interval(dt: datetime, interval: str) -> datetime:
    """Add one month or one year, clamping the day (Jan 31 -> Feb 28)."""
    months = 12 if interval == "year" else 1
    total = dt.month - 1 + months
    year, month = dt.year + total // 12, total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def calculate_change(db: Session, sub: models.Subscription, new_plan_id: int) -> dict:
    old = db.get(models.Plan, sub.plan_id)
    new = db.get(models.Plan, new_plan_id)
    if not new:
        raise ValueError("New plan not found")
    if new.id == old.id:
        raise ValueError("Subscription is already on this plan")
    if new.currency.lower() != old.currency.lower():
        raise ValueError("Changing currency mid-period is not supported")

    now = _naive(datetime.utcnow())
    start, end = _naive(sub.current_period_start), _naive(sub.current_period_end)
    total = (end - start).total_seconds()
    remaining = max((end - now).total_seconds(), 0)
    fraction = remaining / total if total > 0 else 0
    fraction = max(0.0, min(1.0, fraction))

    credit = round(old.amount_cents * fraction)
    if old.interval != new.interval:
        charge = new.amount_cents                     # fresh period, full price
        new_start, new_end = now, add_interval(now, new.interval)
    else:
        charge = round(new.amount_cents * fraction)   # same period, prorated
        new_start, new_end = start, end

    return {
        "from_plan_id": old.id, "to_plan_id": new.id,
        "unused_fraction": round(fraction, 4),
        "credit_cents": credit, "charge_cents": charge, "net_cents": charge - credit,
        "currency": new.currency,
        "new_period_start": new_start, "new_period_end": new_end,
    }


def apply_change(db: Session, sub: models.Subscription, new_plan_id: int):
    c = calculate_change(db, sub, new_plan_id)

    invoice = None
    if c["net_cents"] > 0:
        invoice = models.Invoice(
            subscription_id=sub.id,
            amount_cents=c["net_cents"],
            currency=c["currency"],
            status="open",
            due_date=_naive(datetime.utcnow()),
        )
        db.add(invoice)
        db.flush()

    sub.plan_id = c["to_plan_id"]
    sub.current_period_start = c["new_period_start"]
    sub.current_period_end = c["new_period_end"]

    db.add(models.PlanChange(
        subscription_id=sub.id,
        from_plan_id=c["from_plan_id"], to_plan_id=c["to_plan_id"],
        credit_cents=c["credit_cents"], charge_cents=c["charge_cents"],
        net_cents=c["net_cents"], invoice_id=invoice.id if invoice else None,
    ))
    db.commit()
    return c, invoice