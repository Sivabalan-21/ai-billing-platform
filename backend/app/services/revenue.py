from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models


def add_months(year: int, month: int, n: int) -> str:
    total = year * 12 + (month - 1) + n
    return f"{total // 12}-{total % 12 + 1:02d}"


def months_for(db: Session, invoice: models.Invoice) -> int:
    """How many months this invoice's revenue is earned over."""
    if db.query(models.UsageEvent).filter_by(invoice_id=invoice.id).first():
        return 1                                    # usage already happened
    sub = invoice.subscription
    if db.query(models.PlanChange).filter_by(invoice_id=invoice.id).first():
        now, end = datetime.utcnow(), sub.current_period_end
        return max(1, (end.year - now.year) * 12 + end.month - now.month)
    plan = db.get(models.Plan, sub.plan_id)
    return 12 if plan.interval == "year" else 1


def recognize_invoice(db: Session, invoice: models.Invoice) -> int:
    """Create the monthly revenue schedule for a paid invoice. Returns months scheduled."""
    if invoice.status != "paid" or invoice.amount_cents <= 0:
        return 0
    if db.query(models.RevenueEntry).filter_by(invoice_id=invoice.id).first():
        return 0                                    # already scheduled
    n = months_for(db, invoice)
    base, extra = divmod(invoice.amount_cents, n)
    now = datetime.utcnow()
    for i in range(n):
        db.add(models.RevenueEntry(
            invoice_id=invoice.id,
            subscription_id=invoice.subscription_id,
            currency=invoice.currency.lower(),
            period=add_months(now.year, now.month, i),
            amount_cents=base + (1 if i < extra else 0),   # spread the leftover cents
        ))
    db.commit()
    return n


def backfill(db: Session) -> dict:
    """Schedule revenue for paid invoices that don't have entries yet."""
    done = 0
    for inv in db.query(models.Invoice).filter(models.Invoice.status == "paid").all():
        if recognize_invoice(db, inv):
            done += 1
    return {"invoices_scheduled": done}


def revenue_report(db: Session) -> dict:
    now = datetime.utcnow()
    current = f"{now.year}-{now.month:02d}"
    rows = (
        db.query(models.RevenueEntry.period, models.RevenueEntry.currency,
                 func.sum(models.RevenueEntry.amount_cents))
        .group_by(models.RevenueEntry.period, models.RevenueEntry.currency)
        .order_by(models.RevenueEntry.period)
        .all()
    )
    by_month, totals = [], {}
    for period, currency, amount in rows:
        amount = int(amount)
        recognized = period <= current              # "YYYY-MM" strings sort correctly
        by_month.append({
            "period": period, "currency": currency, "amount_cents": amount,
            "status": "recognized" if recognized else "scheduled",
        })
        t = totals.setdefault(currency, {"recognized_cents": 0, "deferred_cents": 0, "billed_cents": 0})
        t["recognized_cents" if recognized else "deferred_cents"] += amount
        t["billed_cents"] += amount
    return {"as_of": current, "totals": totals, "by_month": by_month}