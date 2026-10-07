from types import SimpleNamespace


class FakeProvider:
    """Stand-in for a payment provider. Never touches the network."""

    def __init__(self, name="stripe", success=True, reason=None, test_payment_method="test-token"):
        self.name = name
        self.success = success
        self.reason = reason
        self.test_payment_method = test_payment_method
        self.charges = []

    def charge(self, customer, amount_cents, currency, payment_method):
        self.charges.append((amount_cents, currency, payment_method))
        return SimpleNamespace(
            success=self.success,
            provider_ref="ref_ok" if self.success else None,
            failure_reason=None if self.success else self.reason,
        )