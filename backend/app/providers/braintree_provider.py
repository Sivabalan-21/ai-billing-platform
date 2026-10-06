from decimal import Decimal
import braintree
from app.config import settings
from app.providers.base import PaymentProvider, PaymentResult


class BraintreeProvider(PaymentProvider):
    """Real Braintree adapter, sandbox environment."""
    name = "braintree"
    simulated = False
    test_payment_method = "fake-valid-nonce"   # Braintree's sandbox test token

    def _gateway(self):
        return braintree.BraintreeGateway(braintree.Configuration(
            environment=braintree.Environment.Sandbox,
            merchant_id=settings.braintree_merchant_id,
            public_key=settings.braintree_public_key,
            private_key=settings.braintree_private_key,
        ))

    def charge(self, customer, amount_cents, currency, payment_method):
        if not settings.braintree_merchant_id:
            return PaymentResult(False, failure_reason="braintree_not_configured")
        try:
            amount = (Decimal(amount_cents) / Decimal(100)).quantize(Decimal("0.01"))
            params = {
                "amount": str(amount),
                "payment_method_nonce": payment_method,
                "options": {"submit_for_settlement": True},
            }
            if settings.braintree_merchant_account_id:
                params["merchant_account_id"] = settings.braintree_merchant_account_id

            result = self._gateway().transaction.sale(params)
            if result.is_success:
                return PaymentResult(True, provider_ref=result.transaction.id)

            txn = result.transaction
            if txn is not None:
                if txn.gateway_rejection_reason:
                    g = txn.gateway_rejection_reason
                    reason = "fraudulent" if g == "fraud" else f"gateway_{g}"
                else:
                    reason = (txn.processor_response_text or txn.status or "declined")
                    reason = reason.lower().replace(" ", "_")
                return PaymentResult(False, provider_ref=txn.id, failure_reason=reason[:120])
            return PaymentResult(False, failure_reason=str(result.message)[:120])
        except Exception as e:
            return PaymentResult(False, failure_reason=str(getattr(e, "code", None) or e)[:120])