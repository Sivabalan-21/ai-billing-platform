from app.providers.stripe_provider import StripeProvider
from app.providers.braintree_provider import BraintreeProvider
from app.providers.mock_provider import MockProvider

DEFAULT_PROVIDER = "stripe"

_PROVIDERS = {
    p.name: p
    for p in [
        StripeProvider(),
        BraintreeProvider(),
        MockProvider("recurly"),
        MockProvider("chargebee"),
        MockProvider("zuora"),
    ]
}


def get_provider(name: str = DEFAULT_PROVIDER):
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown payment provider: {name}. Available: {sorted(_PROVIDERS)}")
    return _PROVIDERS[name]


def list_providers() -> list[dict]:
    return [
        {"name": p.name, "mode": "simulated" if getattr(p, "simulated", False) else "sandbox/test"}
        for p in _PROVIDERS.values()
    ]