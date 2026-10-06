from app.providers.stripe_provider import StripeProvider

_PROVIDERS = {"stripe": StripeProvider()}


def get_provider(name: str = "stripe"):
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown payment provider: {name}")
    return _PROVIDERS[name]