from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.services.usage import record_usage, usage_summary, bill_usage

router = APIRouter(tags=["usage"])


class UsageIn(BaseModel):
    subscription_id: int
    quantity: int = Field(gt=0)
    event_key: str | None = None


def _get_active_sub(db: Session, subscription_id: int):
    sub = db.get(models.Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    if sub.status == "canceled":
        raise HTTPException(400, "Subscription is canceled")
    return sub


@router.post("/usage")
def add_usage(data: UsageIn, db: Session = Depends(get_db)):
    _get_active_sub(db, data.subscription_id)
    e = record_usage(db, data.subscription_id, data.quantity, data.event_key)
    return {"id": e.id, "quantity": e.quantity, "event_key": e.event_key}


@router.get("/subscriptions/{subscription_id}/usage")
def get_usage(subscription_id: int, month: str | None = None, db: Session = Depends(get_db)):
    _get_active_sub(db, subscription_id)
    return usage_summary(db, subscription_id, month)


@router.post("/subscriptions/{subscription_id}/usage/invoice")
def invoice_usage(subscription_id: int, month: str | None = None, db: Session = Depends(get_db)):
    _get_active_sub(db, subscription_id)
    invoice = bill_usage(db, subscription_id, month)
    if invoice is None:
        return {"invoice_id": None, "message": "Usage is within the free allowance, nothing to bill"}
    return {"invoice_id": invoice.id, "amount_cents": invoice.amount_cents, "status": invoice.status}   