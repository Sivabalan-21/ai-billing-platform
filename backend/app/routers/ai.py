from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.services.churn import score_subscription
from app.services.retention import send_offers
from app.services.forecasts import predict_payment_failure, estimate_clv, failure_watchlist
from app.services.pricing import pricing_suggestions, explain

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

@router.get("/ai/payment-risk")
def payment_risk_watchlist(days_ahead: int = 7, min_risk: float = 0.3, db: Session = Depends(get_db)):
    """Subscriptions renewing soon that are likely to be declined."""
    return failure_watchlist(db, days_ahead, min_risk)

@router.get("/ai/payment-risk/{subscription_id}")
def payment_risk_one(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.get(models.Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    return predict_payment_failure(db, sub)


@router.get("/ai/clv")
def clv_list(db: Session = Depends(get_db)):
    subs = (db.query(models.Subscription)
            .filter(models.Subscription.status.in_(["active", "past_due"])).all())
    rows = [estimate_clv(db, s) for s in subs]
    return sorted(rows, key=lambda r: -r["clv_cents"])


@router.get("/ai/clv/{subscription_id}")
def clv_one(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.get(models.Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    return estimate_clv(db, sub)

@router.get("/ai/pricing-suggestions")
def pricing(min_subs: int = 3, explain_with_ai: bool = True, db: Session = Depends(get_db)):
    """min_subs: minimum customers per plan before we judge it (use 1 for test data)."""
    result = pricing_suggestions(db, min_subs)
    if explain_with_ai:
        text, source = explain(result)
        result["explanation"] = {"text": text, "source": source}
    return result

@router.get("/subscriptions")
def list_subscriptions(db: Session = Depends(get_db)):
    plans = {p.id: p for p in db.query(models.Plan).all()}
    rows = []
    for s in db.query(models.Subscription).order_by(models.Subscription.id).all():
        p = plans.get(s.plan_id)
        rows.append({
            "id": s.id,
            "customer_id": getattr(s, "customer_id", None),
            "plan_id": s.plan_id,
            "plan_name": getattr(p, "name", f"Plan {s.plan_id}") if p else None,
            "status": s.status,
            "current_period_end": getattr(s, "current_period_end", None),
        })
    return rows


@router.get("/subscriptions/{subscription_id}/overview")
def subscription_overview(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.get(models.Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")

    def safe(fn):
        try:
            return fn(db, sub)
        except Exception as e:
            return {"error": str(e)}

    return {
        "id": sub.id,
        "customer_id": getattr(sub, "customer_id", None),
        "plan_id": sub.plan_id,
        "status": sub.status,
        "current_period_end": getattr(sub, "current_period_end", None),
        "churn": safe(score_subscription),
        "payment_risk": safe(predict_payment_failure),
        "clv": safe(estimate_clv),
    }   