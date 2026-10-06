from datetime import datetime
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.services.dunning import run_dunning
from app.services.payments import pay_invoice
from app.services.renewals import renew_due, sub_currency
from app.services.revenue import add_months
from app.services.trials import run_trials
from app.services.usage import bill_usage


def bill_usage_all(db: Session, payment_method: str) -> list[dict]:
    """Bill last month's unbilled usage for every active subscription."""
    now = datetime.utcnow()
    month = add_months(now.year, now.month, -1)
    report = []
    for sub in db.query(models.Subscription).filter(models.Subscription.status == "active").all():
        try:
            invoice = bill_usage(db, sub.id, month, sub_currency(db, sub))
            if invoice:
                payment = pay_invoice(db, invoice, payment_method)
                report.append({"subscription_id": sub.id, "invoice_id": invoice.id,
                               "amount_cents": invoice.amount_cents, "result": payment.status})
        except Exception as e:
            db.rollback()
            report.append({"subscription_id": sub.id, "result": "error", "reason": str(e)[:150]})
    return report


def run_daily(db: Session) -> dict:
    pm = settings.default_payment_method
    steps = [
        ("trials", lambda: run_trials(db, pm)),
        ("renewals", lambda: renew_due(db, pm)),
        ("usage", lambda: bill_usage_all(db, pm)),
        ("dunning", lambda: run_dunning(db, pm)),
    ]
    report = {}
    for name, fn in steps:
        try:
            report[name] = fn()
        except Exception as e:
            db.rollback()
            report[name] = {"error": str(e)[:200]}  # one failing step doesn't stop the others
    return report