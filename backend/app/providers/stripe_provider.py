from pdb import pm

import stripe
from app.config import settings
from app.providers.base import PaymentProvider, PaymentResult


class StripeProvider(PaymentProvider):
    name = "stripe"

    def charge(self, customer, amount_cents, currency, payment_method):
        stripe.api_key = settings.stripe_secret_key
        try:
            if not customer.stripe_customer_id:
                sc = stripe.Customer.create(email=customer.email, name=customer.name)
                customer.stripe_customer_id = sc.id

            pm = stripe.PaymentMethod.attach(payment_method, customer=customer.stripe_customer_id)
            intent = stripe.PaymentIntent.create(
    amount=amount_cents,
    currency=currency.lower(),
    customer=customer.stripe_customer_id,
    payment_method=pm.id,
    confirm=True,
    off_session=True,
    automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
)
            if intent.status == "succeeded":
                return PaymentResult(True, provider_ref=intent.id)
            return PaymentResult(False, provider_ref=intent.id, failure_reason=intent.status)
        except Exception as e:
            reason = getattr(e, "decline_code", None) or getattr(e, "code", None) or str(e)
            return PaymentResult(False, failure_reason=str(reason)[:120])