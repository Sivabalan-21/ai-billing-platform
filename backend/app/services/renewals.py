from datetime import datetime
from sqlalchemy.orm import Session
from app import models
from app.services.payments import pay_invoice
from app.services.plan_changes import add_interval
from app.services.trials import price_for


def _naive(dt):
    return dt.replace(tzinfo=None) if dt else None


def sub_currency(db: Session, sub: models.Subscription) -> str:
    trial = db.query(models.Trial).filter_by(subscription_id=sub.id).first()
    plan = db.get(models.Plan, sub.plan_id)
    return (trial.currency if trial else plan.currency).lower()


def _unapplied_credits(db: Session, subscription_id: int):
    used = {c.plan_change_id for c in db.query(models.CreditApplication).all()}
    changes = (
        db.query(models.PlanChange)
        .filter(models.PlanChange.subscription_id == subscription_id,
                models.PlanChange.net_cents < 0)
        .order_by(models.PlanChange.id)
        .all()
    )
    return [c for c in changes if c.id not in used]


def renew_due(db: Session, payment_method: str, subscription_id: int | None = None,
              force: bool = False) -> list[dict]:
    """Invoice and charge active subscriptions whose period has ended.
    force=True with a subscription_id renews that one now (for testing)."""
    now = datetime.utcnow()
    q = db.query(models.Subscription).filter(models.Subscription.status == "active")
    if force and subscription_id:
        q = q.filter(models.Subscription.id == subscription_id)
    else:
        q = q.filter(models.Subscription.current_period_end <= now)

    report = []
    for sub in q.all():
        try:
            plan = db.get(models.Plan, sub.plan_id)
            currency = sub_currency(db, sub)
            amount = price_for(db, plan, currency)

            # apply stored credits, but only ones that leave something to pay
            remaining, used = amount, []
            for pc in _unapplied_credits(db, sub.id):
                if -pc.net_cents < remaining:
                    used.append(pc)
                    remaining -= -pc.net_cents

            start = _naive(sub.current_period_end)
            sub.current_period_start = start
            sub.current_period_end = add_interval(start, plan.interval)

            invoice = models.Invoice(subscription_id=sub.id, amount_cents=remaining,
                                     currency=currency, status="open", due_date=start)
            db.add(invoice)
            db.flush()
            for pc in used:
                db.add(models.CreditApplication(plan_change_id=pc.id, invoice_id=invoice.id,
                                                amount_cents=-pc.net_cents))
            db.commit()
            db.refresh(invoice)

            payment = pay_invoice(db, invoice, payment_method)
            report.append({"subscription_id": sub.id, "invoice_id": invoice.id,
                           "amount_cents": remaining, "credit_applied_cents": amount - remaining,
                           "result": payment.status})
        except Exception as e:
            db.rollback()
            report.append({"subscription_id": sub.id, "result": "error", "reason": str(e)[:150]})
    return report