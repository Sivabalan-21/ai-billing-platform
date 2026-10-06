from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.services.trials import set_price, start_trial, run_trials, trial_usage

router = APIRouter(tags=["trials & currencies"])

SUPPORTED_CURRENCIES = {"usd", "eur", "inr"}


class PriceIn(BaseModel):
    currency: str
    amount_cents: int = Field(gt=0)


class TrialIn(BaseModel):
    customer_id: int
    plan_id: int
    trial_days: int = Field(default=14, ge=1, le=90)
    currency: str = "usd"


def _check_currency(c: str) -> str:
    c = c.lower()
    if c not in SUPPORTED_CURRENCIES:
        raise HTTPException(400, f"Unsupported currency. Use one of: {sorted(SUPPORTED_CURRENCIES)}")
    return c


@router.post("/plans/{plan_id}/prices")
def add_price(plan_id: int, data: PriceIn, db: Session = Depends(get_db)):
    try:
        row = set_price(db, plan_id, _check_currency(data.currency), data.amount_cents)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"plan_id": row.plan_id, "currency": row.currency, "amount_cents": row.amount_cents}


@router.get("/plans/{plan_id}/prices")
def list_prices(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(models.Plan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    rows = db.query(models.PlanPrice).filter_by(plan_id=plan_id).all()
    prices = {plan.currency.lower(): plan.amount_cents}
    prices.update({r.currency: r.amount_cents for r in rows})
    return prices


@router.post("/trials")
def create_trial(data: TrialIn, db: Session = Depends(get_db)):
    currency = _check_currency(data.currency)
    try:
        sub, trial = start_trial(db, data.customer_id, data.plan_id, data.trial_days, currency)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"subscription_id": sub.id, "status": sub.status,
            "trial_end": trial.trial_end.isoformat(), "currency": trial.currency}


@router.get("/trials")
def list_trials(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    out = []
    for t in db.query(models.Trial).all():
        units = trial_usage(db, t.subscription_id)
        out.append({
            "subscription_id": t.subscription_id,
            "trial_end": t.trial_end.isoformat(),
            "days_left": max((t.trial_end - now).days, 0),
            "converted": t.converted,
            "usage_units": units,
            "at_risk": (not t.converted) and units == 0,  # no usage = unlikely to convert
        })
    return out


@router.post("/trials/run")
def run(payment_method: str = "pm_card_visa", force: bool = False, db: Session = Depends(get_db)):
    return run_trials(db, payment_method, force)