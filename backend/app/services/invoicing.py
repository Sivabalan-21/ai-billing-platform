from datetime import datetime
from sqlalchemy.orm import Session
from app import models
from app.services.billing import period_end


def generate_due_invoices(db: Session, now: datetime) -> list[models.Invoice]:
    due = (
        db.query(models.Subscription)
        .filter(models.Subscription.status.in_(["active", "trialing"]))
        .filter(models.Subscription.current_period_end <= now)
        .all()
    )

    created = []
    for sub in due:
        plan = sub.plan
        invoice = models.Invoice(
            subscription_id=sub.id,
            amount_cents=plan.amount_cents,
            currency=plan.currency,
            status="open",
            due_date=now,
        )
        db.add(invoice)
        created.append(invoice)

        # roll the subscription into its next period (trial -> paid happens here)
        sub.current_period_start = sub.current_period_end
        sub.current_period_end = period_end(sub.current_period_start, plan.interval)
        sub.status = "active"

    db.commit()
    for invoice in created:
        db.refresh(invoice)
    return created