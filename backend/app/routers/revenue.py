from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.revenue import backfill, revenue_report

router = APIRouter(tags=["revenue"])


@router.get("/revenue/report")
def report(db: Session = Depends(get_db)):
    return revenue_report(db)


@router.post("/revenue/backfill")
def run_backfill(db: Session = Depends(get_db)):
    return backfill(db)