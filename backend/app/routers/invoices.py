from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services.billing import utcnow
from app.services.invoicing import generate_due_invoices

from app.services.payments import pay_invoice   

router = APIRouter()


@router.get("/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(subscription_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Invoice)
    if subscription_id:
        query = query.filter_by(subscription_id=subscription_id)
    return query.order_by(models.Invoice.id.desc()).all()


@router.post("/billing/run")
def run_billing(days_ahead: int = 0, db: Session = Depends(get_db)):
    """Manual trigger. days_ahead fakes time passing, so you can test without waiting a month."""
    now = utcnow() + timedelta(days=days_ahead)
    created = generate_due_invoices(db, now)
    return {"invoices_created": len(created), "invoice_ids": [i.id for i in created]}

@router.post("/invoices/{invoice_id}/pay", response_model=schemas.PaymentOut)
def pay(invoice_id: int, data: schemas.PayIn, db: Session = Depends(get_db)):
    invoice = db.get(models.Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice.status == "paid":
        raise HTTPException(400, "Invoice already paid")
    try:
        return pay_invoice(db, invoice, data.payment_method, data.provider)
    except ValueError as e:
        raise HTTPException(400, str(e))