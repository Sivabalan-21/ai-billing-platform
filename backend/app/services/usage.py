from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models

# (cumulative upper limit, cents per unit). None = no upper limit.
TIERS = [(1000, 0), (10000, 2), (None, 1)]


def price_usage(total_units: int) -> int:
    """Tiered pricing: returns the charge in cents for a month's total units."""
    cents, lower = 0, 0
    for upper, rate in TIERS:
        if total_units <= lower:
            break
        top = total_units if upper is None else min(total_units, upper)
        cents += (top - lower) * rate
        if upper is None:
            break
        lower = upper
    return cents


def month_range(month: str | None):
    """'2026-10' -> (start, end). Defaults to the current month."""
    now = datetime.utcnow()
    y, m = (now.year, now.month) if not month else map(int, month.split("-"))
    start = datetime(y, m, 1)
    end = datetime(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return start, end


def record_usage(db: Session, subscription_id: int, quantity: int, event_key: str | None):
    if event_key:
        existing = db.query(models.UsageEvent).filter_by(event_key=event_key).first()
        if existing:
            return existing  # same event sent twice: count it once
    event = models.UsageEvent(subscription_id=subscription_id, quantity=quantity, event_key=event_key)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _unbilled(db: Session, subscription_id: int, month: str | None):
    start, end = month_range(month)
    return (
        db.query(models.UsageEvent)
        .filter(
            models.UsageEvent.subscription_id == subscription_id,
            models.UsageEvent.invoice_id.is_(None),
            models.UsageEvent.recorded_at >= start,
            models.UsageEvent.recorded_at < end,
        )
        .all()
    )


def usage_summary(db: Session, subscription_id: int, month: str | None = None) -> dict:
    events = _unbilled(db, subscription_id, month)
    total = sum(e.quantity for e in events)
    return {"units": total, "amount_cents": price_usage(total), "events": len(events)}


def bill_usage(db: Session, subscription_id: int, month: str | None = None, currency: str = "usd"):
    events = _unbilled(db, subscription_id, month)
    total = sum(e.quantity for e in events)
    amount = price_usage(total)
    if amount == 0:
        return None  # inside the free allowance, nothing to bill

    invoice = models.Invoice(
        subscription_id=subscription_id,
        amount_cents=amount,
        currency=currency,
        status="open",
    )
    db.add(invoice)
    db.flush()  # gives the invoice an id
    for e in events:
        e.invoice_id = invoice.id  # mark as billed so it can't be billed twice
    db.commit()
    db.refresh(invoice)
    return invoice