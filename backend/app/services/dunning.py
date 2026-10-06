from datetime import timedelta
from sqlalchemy.orm import Session
from app import models
from app.services.billing import utcnow
from app.services.payments import pay_invoice

RETRY_DELAYS_DAYS = [1, 3, 5, 7]          # wait after attempt 1, 2, 3, 4
MAX_ATTEMPTS = len(RETRY_DELAYS_DAYS) + 1  # 5 total tries

HARD_DECLINES = {
    "lost_card", "stolen_card", "pickup_card", "fraudulent",
    "expired_card", "invalid_account", "card_not_supported",
}


def _naive(dt):
    return dt.replace(tzinfo=None) if dt else None


def plan_for(invoice: models.Invoice) -> dict | None:
    """Decide what should happen next for a failed invoice."""
    if not invoice.payments:
        return None
    last = max(invoice.payments, key=lambda p: p.attempt_no)
    attempts = last.attempt_no

    if last.failure_reason in HARD_DECLINES:
        return {"action": "needs_new_card", "retry_at": None, "attempts": attempts}
    if attempts >= MAX_ATTEMPTS:
        return {"action": "give_up", "retry_at": None, "attempts": attempts}

    retry_at = _naive(last.created_at) + timedelta(days=RETRY_DELAYS_DAYS[attempts - 1])
    return {"action": "retry", "retry_at": retry_at, "attempts": attempts}


def _give_up(db: Session, invoice: models.Invoice):
    invoice.status = "uncollectible"
    invoice.subscription.status = "canceled"
    db.commit()


def run_dunning(db: Session, payment_method: str, force: bool = False) -> list[dict]:
    """Retry every failed invoice that is due. force=True ignores the schedule (for testing)."""
    now = _naive(utcnow())
    failed = db.query(models.Invoice).filter(models.Invoice.status == "failed").all()
    report = []

    for inv in failed:
        plan = plan_for(inv)
        if plan is None:
            continue

        if plan["action"] == "give_up":
            _give_up(db, inv)
            report.append({"invoice_id": inv.id, "result": "gave_up"})
            continue
        if plan["action"] == "needs_new_card":
            report.append({"invoice_id": inv.id, "result": "needs_new_card"})
            continue
        if not force and now < plan["retry_at"]:
            report.append({"invoice_id": inv.id, "result": "not_due_yet",
                           "retry_at": plan["retry_at"].isoformat()})
            continue

        payment = pay_invoice(db, inv, payment_method)
        if payment.status == "succeeded":
            report.append({"invoice_id": inv.id, "result": "recovered",
                           "attempt_no": payment.attempt_no})
        elif payment.attempt_no >= MAX_ATTEMPTS:
            _give_up(db, inv)
            report.append({"invoice_id": inv.id, "result": "gave_up",
                           "attempt_no": payment.attempt_no})
        else:
            report.append({"invoice_id": inv.id, "result": "retry_failed",
                           "attempt_no": payment.attempt_no,
                           "reason": payment.failure_reason})
    return report