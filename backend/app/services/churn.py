from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models

FEATURES = ["days_since_last_usage", "usage_30d", "failed_payments", "plan_age_days", "downgrades"]
_model = None


def _train():
    """Train on synthetic data (no real cancellation history exists yet)."""
    rng = np.random.default_rng(42)
    n = 4000
    days = np.clip(rng.exponential(12, n), 0, 90)
    usage = rng.exponential(2000, n) * np.exp(-days / 20)
    failed = rng.poisson(0.4, n)
    age = rng.uniform(0, 720, n)
    down = rng.poisson(0.15, n)
    logit = -2.0 + 0.10 * days + 0.8 * failed + 1.0 * down - 0.0005 * usage - 0.0015 * age
    y = rng.random(n) < 1 / (1 + np.exp(-logit))
    X = np.column_stack([days, usage, failed, age, down])
    return make_pipeline(StandardScaler(), LogisticRegression()).fit(X, y)


def get_model():
    global _model
    if _model is None:
        _model = _train()
    return _model


def _start(sub):
    for attr in ("created_at", "start_date"):
        v = getattr(sub, attr, None)
        if v:
            return v.replace(tzinfo=None)
    return (sub.current_period_start or datetime.utcnow()).replace(tzinfo=None)


def extract_features(db: Session, sub: models.Subscription) -> dict:
    now = datetime.utcnow()
    age = max((now - _start(sub)).days, 0)

    last = (db.query(func.max(models.UsageEvent.recorded_at))
            .filter(models.UsageEvent.subscription_id == sub.id).scalar())
    days_since = (now - last).days if last else age
    usage_30d = (db.query(func.coalesce(func.sum(models.UsageEvent.quantity), 0))
                 .filter(models.UsageEvent.subscription_id == sub.id,
                         models.UsageEvent.recorded_at >= now - timedelta(days=30))
                 .scalar())
    failed = (db.query(func.count(models.Payment.id))
              .join(models.Invoice, models.Payment.invoice_id == models.Invoice.id)
              .filter(models.Invoice.subscription_id == sub.id, models.Payment.status == "failed")
              .scalar())
    downgrades = (db.query(func.count(models.PlanChange.id))
                  .filter(models.PlanChange.subscription_id == sub.id,
                          models.PlanChange.net_cents < 0).scalar())
    return {
        "days_since_last_usage": min(days_since, 90),
        "usage_30d": int(usage_30d),
        "failed_payments": int(failed),
        "plan_age_days": age,
        "downgrades": int(downgrades),
    }


def _reason_text(k: str, f: dict) -> str:
    return {
        "days_since_last_usage": f"no usage in {int(f[k])} days",
        "usage_30d": f"low usage in the last 30 days ({int(f[k])} units)",
        "failed_payments": f"{int(f[k])} failed payment(s)",
        "plan_age_days": "a fairly new customer",
        "downgrades": "recently downgraded their plan",
    }[k]


def score_subscription(db: Session, sub: models.Subscription, overrides: dict | None = None) -> dict:
    f = extract_features(db, sub)
    f.update({k: v for k, v in (overrides or {}).items() if v is not None})

    x = np.array([[f[k] for k in FEATURES]], dtype=float)
    model = get_model()
    risk = float(model.predict_proba(x)[0, 1])

    # contribution of each feature compared with a typical customer
    scaler, lr = model.steps[0][1], model.steps[1][1]
    contrib = lr.coef_[0] * scaler.transform(x)[0]
    ranked = sorted(zip(FEATURES, contrib), key=lambda t: -t[1])
    reasons = [_reason_text(k, f) for k, c in ranked if c > 0.2][:3]

    return {
        "subscription_id": sub.id,
        "risk": round(risk, 3),
        "risk_percent": round(risk * 100),
        "level": "high" if risk >= 0.7 else "medium" if risk >= 0.4 else "low",
        "reasons": reasons,
        "features": f,
    }