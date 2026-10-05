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