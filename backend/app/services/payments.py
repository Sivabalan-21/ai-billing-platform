from sqlalchemy.orm import Session
from app import models
from app.providers.registry import get_provider, DEFAULT_PROVIDER
from app.services.billing import utcnow
from app.services.emails import notify_payment
from app.services.revenue import recognize_invoice


def pay_invoice(db: Session, invoice: models.Invoice, payment_method: str,
                provider_name: str | None = None):
    # No provider given: reuse the one this invoice last used (so dunning retries match).
    if provider_name is None:
        provider_name = (
            max(invoice.payments, key=lambda p: p.attempt_no).provider
            if invoice.payments else DEFAULT_PROVIDER
        )
    provider = get_provider(provider_name)

    # Test-mode shim: scheduled jobs pass Stripe's "pm_card_visa" by default. For other
    # providers, swap in that provider's own test token. Removed once customers have
    # real saved payment methods.
    if provider.name != "stripe" and payment_method.startswith("pm_"):
        payment_method = getattr(provider, "test_payment_method", payment_method)

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
    notify_payment(db, invoice, payment)
    return payment