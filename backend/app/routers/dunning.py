from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models
from app.database import get_db  # <- use YOUR exact line from invoices.py
from app.services.dunning import plan_for, run_dunning

router = APIRouter(tags=["dunning"])


@router.get("/dunning/queue")
def queue(db: Session = Depends(get_db)):
    failed = db.query(models.Invoice).filter(models.Invoice.status == "failed").all()
    out = []
    for inv in failed:
        plan = plan_for(inv)
        if plan:
            out.append({
                "invoice_id": inv.id,
                "action": plan["action"],
                "attempts": plan["attempts"],
                "retry_at": plan["retry_at"].isoformat() if plan["retry_at"] else None,
            })
    return out


@router.post("/dunning/run")
def run(payment_method: str = "pm_card_visa", force: bool = False, db: Session = Depends(get_db)):
    return run_dunning(db, payment_method, force)