from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.services.plan_changes import calculate_change, apply_change

router = APIRouter(tags=["plan changes"])


class ChangePlanIn(BaseModel):
    new_plan_id: int


def _active_sub(db: Session, subscription_id: int):
    sub = db.get(models.Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    if sub.status == "canceled":
        raise HTTPException(400, "Subscription is canceled")
    return sub


@router.get("/subscriptions/{subscription_id}/change-plan/preview")
def preview(subscription_id: int, new_plan_id: int, db: Session = Depends(get_db)):
    sub = _active_sub(db, subscription_id)
    try:
        c = calculate_change(db, sub, new_plan_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in c.items()}


@router.post("/subscriptions/{subscription_id}/change-plan")
def change_plan(subscription_id: int, data: ChangePlanIn, db: Session = Depends(get_db)):
    sub = _active_sub(db, subscription_id)
    try:
        c, invoice = apply_change(db, sub, data.new_plan_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "credit_cents": c["credit_cents"], "charge_cents": c["charge_cents"],
        "net_cents": c["net_cents"],
        "invoice_id": invoice.id if invoice else None,
        "message": "Pay the invoice to complete the upgrade" if invoice
                   else "Credit recorded, applied to the next renewal",
    }