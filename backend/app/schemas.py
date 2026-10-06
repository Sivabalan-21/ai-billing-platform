from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PlanIn(BaseModel):
    name: str
    amount_cents: int
    currency: str = "USD"
    interval: Literal["month", "year"] = "month"
    trial_days: int = 0


class PlanOut(PlanIn, ORM):
    id: int


class CustomerIn(BaseModel):
    email: str
    name: str
    currency: str = "USD"


class CustomerOut(CustomerIn, ORM):
    id: int


class SubscriptionIn(BaseModel):
    customer_id: int
    plan_id: int


class ChangePlanIn(BaseModel):
    new_plan_id: int


class SubscriptionOut(ORM):
    id: int
    customer_id: int
    plan_id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    trial_end: datetime | None
    canceled_at: datetime | None


class InvoiceOut(ORM):
    id: int
    subscription_id: int
    amount_cents: int
    currency: str
    status: str
    due_date: datetime
    paid_at: datetime | None
    created_at: datetime | None

class PayIn(BaseModel):
    payment_method: str = "pm_card_visa"


class PaymentOut(ORM):
    id: int
    invoice_id: int
    amount_cents: int
    status: str
    provider: str
    provider_ref: str | None
    failure_reason: str | None
    attempt_no: int
    created_at: datetime | None