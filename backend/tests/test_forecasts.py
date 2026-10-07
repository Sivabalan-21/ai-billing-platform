from app.services.churn import score_subscription
from app.services.dunning import HARD_DECLINES
from app.services.forecasts import (
    MAX_LIFETIME_MONTHS,
    estimate_clv,
    failure_watchlist,
    predict_payment_failure,
)

SOFT_REASON = "test_soft_decline"   # deliberately not a real hard-decline code


# ---- payment failure prediction ----

def test_clean_history_is_low_risk(db, make):
    r = predict_payment_failure(db, make.sub(make.plan()))
    assert r["features"]["past_failures"] == 0
    assert r["failure_risk"] < 0.3
    assert r["level"] == "low"


def test_repeated_failures_raise_risk(db, make):
    clean = predict_payment_failure(db, make.sub(make.plan()))["failure_risk"]

    sub = make.sub(make.plan())
    inv = make.invoice(sub, status="failed")
    for attempt in (1, 2, 3):
        make.payment(inv, "failed", SOFT_REASON, attempt_no=attempt)

    r = predict_payment_failure(db, sub)
    assert r["features"]["past_failures"] == 3
    assert r["features"]["attempts_last_invoice"] == 3
    assert r["failure_risk"] > clean


def test_hard_decline_forces_high_risk(db, make):
    sub = make.sub(make.plan())
    inv = make.invoice(sub, status="failed")
    make.payment(inv, "failed", sorted(HARD_DECLINES)[0])

    r = predict_payment_failure(db, sub)
    assert r["failure_risk"] >= 0.95
    assert r["level"] == "high"
    assert "new card" in r["advice"].lower()


# ---- customer lifetime value ----

def test_monthly_plan_revenue(db, make):
    r = estimate_clv(db, make.sub(make.plan(amount=9900, interval="month")))
    assert r["monthly_revenue_cents"] == 9900


def test_yearly_plan_is_divided_by_twelve(db, make):
    r = estimate_clv(db, make.sub(make.plan(amount=120000, interval="year")))
    assert r["monthly_revenue_cents"] == 10000


def test_clv_is_paid_plus_future_and_ignores_unpaid(db, make):
    sub = make.sub(make.plan())
    make.invoice(sub, amount=5000, status="paid")
    make.invoice(sub, amount=3000, status="open")

    r = estimate_clv(db, sub)
    assert r["paid_to_date_cents"] == 5000
    assert r["clv_cents"] == 5000 + r["expected_future_revenue_cents"]


def test_lifetime_stays_within_bounds(db, make):
    r = estimate_clv(db, make.sub(make.plan()))
    assert 1 <= r["expected_lifetime_months"] <= MAX_LIFETIME_MONTHS


def test_clv_reuses_the_churn_score(db, make):
    sub = make.sub(make.plan())
    assert (
        estimate_clv(db, sub)["churn_risk_percent"]
        == score_subscription(db, sub)["risk_percent"]
    )


# ---- watchlist ----

def test_watchlist_includes_charges_due_soon(db, make):
    sub = make.sub(make.plan(), days_to_renewal=10)
    ids = [r["subscription_id"] for r in failure_watchlist(db, days_ahead=30, min_risk=0)]
    assert sub.id in ids


def test_watchlist_skips_charges_too_far_away(db, make):
    sub = make.sub(make.plan(), days_to_renewal=10)
    ids = [r["subscription_id"] for r in failure_watchlist(db, days_ahead=3, min_risk=0)]
    assert sub.id not in ids


def test_watchlist_skips_canceled(db, make):
    sub = make.sub(make.plan(), status="canceled", days_to_renewal=3)
    ids = [r["subscription_id"] for r in failure_watchlist(db, days_ahead=30, min_risk=0)]
    assert sub.id not in ids


def test_watchlist_is_ranked_riskiest_first(db, make):
    safe = make.sub(make.plan(), days_to_renewal=3)
    risky = make.sub(make.plan(), days_to_renewal=3)
    inv = make.invoice(risky, status="failed")
    for attempt in (1, 2, 3):
        make.payment(inv, "failed", SOFT_REASON, attempt_no=attempt)

    rows = failure_watchlist(db, days_ahead=30, min_risk=0)
    assert [r["subscription_id"] for r in rows][:2] == [risky.id, safe.id]