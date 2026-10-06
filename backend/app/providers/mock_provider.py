import uuid
from app.providers.base import PaymentProvider, PaymentResult


class MockProvider(PaymentProvider):
    """SIMULATED provider. Never contacts the real service.

    Stands in for Recurly / Chargebee / Zuora until real sandbox accounts exist.
    Behaviour is driven by the payment_method string:
      contains 'expired'      -> expired_card (hard decline, dunning stops)
      contains 'insufficient' -> insufficient_funds (soft decline)
      contains 'decline'      -> generic_decline (soft decline)
      anything else           -> approved
    """
    simulated = True
    test_payment_method = "tok_success"

    def __init__(self, name: str):
        self.name = name

    def charge(self, customer, amount_cents, currency, payment_method):
        pm = (payment_method or "").lower()
        if "expired" in pm:
            return PaymentResult(False, failure_reason="expired_card")
        if "insufficient" in pm:
            return PaymentResult(False, failure_reason="insufficient_funds")
        if "decline" in pm:
            return PaymentResult(False, failure_reason="generic_decline")
        return PaymentResult(True, provider_ref=f"{self.name}_sim_{uuid.uuid4().hex[:12]}")