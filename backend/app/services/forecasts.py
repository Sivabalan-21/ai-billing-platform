from datetime import datetime
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models
from app.services.churn import score_subscription
from app.services.dunning import HARD_DECLINES
from app.services.renewals import sub_currency
from app.services.trials import price_for

PF_FEATURES = ["past_failures", "failure_rate", "attempts_last_invoice",
               "days_to_charge", "amount_dollars", "customer_age_days"]
_pf_model = None
MAX_LIFETIME_MONTHS = 60


def _train_pf():
    """Synthetic training data: past failures and big amounts raise decline risk."""
    rng = np.random.default_rng(7)
    n = 5000
    past = rng.poisson(0.5, n)
    total = past + rng.poisson(6, n) + 1
    rate = past / total
    attempts = np.minimum(rng.poisson(0.6, n) + 1, 5)
    days = rng.uniform(0, 30, n)
    amount = rng.exponential(120, n) + 5
    age = rng.uniform(0, 900, n)
    logit = (-3.0 + 3.5 * rate + 0.35 * past + 0.25 * (attempts - 1)
             + 0.004 * amount - 0.0012 * age)
    y = rng.random(n) < 1 / (1 + np.exp(-logit))
    X = np.column_stack([past, rate, attempts, days, amount, age])
    return GradientBoostingClassifier(random_state=7).fit(X, y)


def get_pf_model():
    global _pf_model
    if _pf_model is None:
        _pf_model = _train_pf()
    return _pf_model


def _payment_history(db: Session, sub: models.Subscription):
    base = (db.query(models.Payment)
            .join(models.Invoice, models.Payment.invoice_id == models.Invoice.id)
            .filter(models.Invoice.subscription_id == sub.id))
    failed = base.filter(models.Payment.status == "failed").count()
    total = base.count()
    worst = (db.query(func.max(models.Payment.attempt_no))
             .join(models.Invoice, models.Payment.invoice_id == models.Invoice.id)
             .filter(models.Invoice.subscription_id == sub.id).scalar()) or 1
    last_failure = (base.filter(models.Payment.status == "failed")
                    .order_by(models.Payment.id.desc()).first())
    return failed, total, worst, last_failure


def predict_payment_failure(db: Session, sub: models.Subscription) -> dict:
    now = datetime.utcnow()
    failed, total, worst, last_failure = _payment_history(db, sub)
    plan = db.get(models.Plan, sub.plan_id)
    currency = sub_currency(db, sub)
    try:
        amount = price_for(db, plan, currency)
    except ValueError:
        amount = plan.amount_cents
    end = sub.current_period_end.replace(tzinfo=None) if sub.current_period_end else now
    days_to_charge = max((end - now).days, 0)
    age = max((now - (sub.current_period_start or now).replace(tzinfo=None)).days, 0)
    rate = failed / total if total else 0.0

    f = {"past_failures": failed, "failure_rate": round(rate, 3),
         "attempts_last_invoice": worst, "days_to_charge": days_to_charge,
         "amount_dollars": round(amount / 100, 2), "customer_age_days": age}
    x = np.array([[f[k] for k in PF_FEATURES]], dtype=float)
    risk = float(get_pf_model().predict_proba(x)[0, 1])

    hard = bool(last_failure and last_failure.failure_reason in HARD_DECLINES)
    if hard:
        risk = max(risk, 0.95)   # a known-dead card will fail again
    level = "high" if risk >= 0.6 else "medium" if risk >= 0.3 else "low"
    advice = {
        "high": "Ask the customer to update their card before the charge date.",
        "medium": "Send a heads-up email a few days before the charge.",
        "low": "No action needed.",
    }[level]
    if hard:
        advice = "Last decline was a hard decline, so a new card is needed before charging."
    return {"subscription_id": sub.id, "failure_risk": round(risk, 3),
            "failure_risk_percent": round(risk * 100), "level": level,
            "advice": advice, "next_charge_in_days": days_to_charge, "features": f}


def estimate_clv(db: Session, sub: models.Subscription) -> dict:
    plan = db.get(models.Plan, sub.plan_id)
    currency = sub_currency(db, sub)
    try:
        price = price_for(db, plan, currency)
    except ValueError:
        price = plan.amount_cents
    monthly = price / 12 if plan.interval == "year" else price

    churn = score_subscription(db, sub)
    # convert the churn score into a per-month probability, kept within sane bounds
    monthly_churn = min(max(churn["risk"] * 0.5, 0.02), 0.95)
    lifetime = min(1 / monthly_churn, MAX_LIFETIME_MONTHS)

    paid = (db.query(func.coalesce(func.sum(models.Invoice.amount_cents), 0))
            .filter(models.Invoice.subscription_id == sub.id,
                    models.Invoice.status == "paid").scalar())
    future = round(monthly * lifetime)
    return {"subscription_id": sub.id, "currency": currency,
            "monthly_revenue_cents": round(monthly),
            "churn_risk_percent": churn["risk_percent"],
            "expected_lifetime_months": round(lifetime, 1),
            "paid_to_date_cents": int(paid),
            "expected_future_revenue_cents": future,
            "clv_cents": int(paid) + future}


def failure_watchlist(db: Session, days_ahead: int = 7, min_risk: float = 0.3) -> list[dict]:
    """Active subscriptions renewing soon, ranked by chance the charge fails."""
    out = []
    for sub in db.query(models.Subscription).filter(models.Subscription.status == "active").all():
        p = predict_payment_failure(db, sub)
        if p["next_charge_in_days"] <= days_ahead and p["failure_risk"] >= min_risk:
            out.append(p)
    return sorted(out, key=lambda r: -r["failure_risk"])