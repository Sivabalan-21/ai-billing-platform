from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentResult:
    success: bool
    provider_ref: str | None = None
    failure_reason: str | None = None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def charge(self, customer, amount_cents: int, currency: str, payment_method: str) -> PaymentResult:
        ...