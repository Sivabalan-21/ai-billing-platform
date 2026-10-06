from sqlalchemy.orm import Session
from app import models
from app.providers.registry import get_provider
from app.services.billing import utcnow
from app.services.revenue import recognize_invoice


def pay_invoice(db: Session, invoice: models.Invoice, payment_method: str, provider_name: str = "stripe"):
    provider = get_provider(provider_name)
    sub = invoice.subscription
    attempt_no = len(invoice.payments) + 1

    result = provider.charge(sub.customer, invoice.amount_cents, invoice.currency, payment_method)

    payment = models.Payment(
        invoice_id=invoice.id,
        amount_cents=invoice.amount_cents,
        status="succeeded" if result.success else "failed",
        provider=provider.name,
        provider_ref=result.provider_ref,
        failure_reason=result.failure_reason,
        attempt_no=attempt_no,
    )
    db.add(payment)

    if result.success:
        invoice.status = "paid"
        invoice.paid_at = utcnow()
        if sub.status == "past_due":
            sub.status = "active"
    else:
        invoice.status = "failed"
        sub.status = "past_due"
    db.commit()
    db.refresh(payment)
    if result.success:
        recognize_invoice(db, invoice)
    return payment