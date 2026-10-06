from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.config import settings
from app.services.jobs import run_daily
from app.services.renewals import renew_due

router = APIRouter(tags=["jobs & emails"])


@router.post("/jobs/run-daily")
def daily(db: Session = Depends(get_db)):
    return run_daily(db)


@router.post("/jobs/renew")
def renew(subscription_id: int | None = None, force: bool = False, db: Session = Depends(get_db)):
    return renew_due(db, settings.default_payment_method, subscription_id, force)


@router.get("/emails")
def emails(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(models.EmailLog).order_by(models.EmailLog.id.desc()).limit(limit).all()
    return [{"id": r.id, "to": r.to_email, "subject": r.subject,
             "status": r.status, "error": r.error, "body": r.body} for r in rows]   