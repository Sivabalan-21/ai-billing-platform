from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.services.churn import score_subscription
from app.services.retention import send_offers

router = APIRouter(tags=["ai"])


@router.get("/ai/churn")
def churn_list(db: Session = Depends(get_db)):
    subs = (db.query(models.Subscription)
            .filter(models.Subscription.status.in_(["active", "past_due", "trialing"])).all())
    rows = [score_subscription(db, s) for s in subs]
    return sorted(rows, key=lambda r: -r["risk"])


@router.get("/ai/churn/{subscription_id}")
def churn_one(subscription_id: int,
              days_since_last_usage: int | None = None,
              failed_payments: int | None = None,
              db: Session = Depends(get_db)):
    """The two optional parameters are 'what if' overrides for demos."""
    sub = db.get(models.Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    return score_subscription(db, sub, {"days_since_last_usage": days_since_last_usage,
                                        "failed_payments": failed_payments})


@router.post("/ai/churn/retention-offers")
def retention_offers(min_risk: float = 0.7, dry_run: bool = True, db: Session = Depends(get_db)):
    """dry_run=true only previews the emails. Set dry_run=false to really send them."""
    return send_offers(db, min_risk, dry_run)