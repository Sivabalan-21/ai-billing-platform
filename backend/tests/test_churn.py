from datetime import datetime, timedelta, timezone

from app import models
from app.services.churn import extract_features, score_subscription


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def add_usage(db, sub, quantity, days_ago=0.0):
    db.add(models.UsageEvent(
        subscription_id=sub.id,
        quantity=quantity,
        recorded_at=_now() - timedelta(days=days_ago),
    ))
    db.commit()


# ---- feature extraction ----

def test_no_usage_falls_back_to_plan_age(db, make):
    f = extract_features(db, make.sub(make.plan()))
    assert f["usage_30d"] == 0
    assert f["plan_age_days"] == 10
    assert f["days_since_last_usage"] == 10


def test_recent_usage_is_summed(db, make):
    sub = make.sub(make.plan())
    add_usage(db, sub, 300)
    add_usage(db, sub, 200)

    f = extract_features(db, sub)
    assert f["usage_30d"] == 500
    assert f["days_since_last_usage"] == 0


def test_usage_older_than_30_days_is_not_counted(db, make):
    sub = make.sub(make.plan())
    add_usage(db, sub, 999, days_ago=40)

    f = extract_features(db, sub)
    assert f["usage_30d"] == 0
    assert f["days_since_last_usage"] == 40


def test_days_since_usage_is_capped_at_90(db, make):
    sub = make.sub(make.plan())
    add_usage(db, sub, 10, days_ago=200)
    assert extract_features(db, sub)["days_since_last_usage"] == 90


def test_only_failed_payments_are_counted(db, make):
    sub = make.sub(make.plan())
    inv = make.invoice(sub, status="failed")
    make.payment(inv, "failed", "generic_decline", attempt_no=1)
    make.payment(inv, "failed", "generic_decline", attempt_no=2)
    make.payment(inv, "succeeded", attempt_no=3)

    assert extract_features(db, sub)["failed_payments"] == 2


def test_only_negative_plan_changes_count_as_downgrades(db, make):
    plan = make.plan()
    sub = make.sub(plan)
    for net in (-500, 500, 0):
        db.add(models.PlanChange(
            subscription_id=sub.id, from_plan_id=plan.id, to_plan_id=plan.id,
            credit_cents=0, charge_cents=0, net_cents=net,
        ))
    db.commit()

    assert extract_features(db, sub)["downgrades"] == 1


# ---- scoring ----

def test_idle_customer_with_failures_scores_higher_than_engaged_one(db, make):
    engaged = make.sub(make.plan())
    add_usage(db, engaged, 3000)

    troubled = make.sub(make.plan())
    add_usage(db, troubled, 10, days_ago=60)
    inv = make.invoice(troubled, status="failed")
    for attempt in (1, 2, 3):
        make.payment(inv, "failed", "generic_decline", attempt_no=attempt)

    good = score_subscription(db, engaged)
    bad = score_subscription(db, troubled)

    assert bad["risk"] > good["risk"]
    assert good["risk"] < 0.4
    assert bad["level"] in ("medium", "high")


def test_overrides_change_the_score(db, make):
    sub = make.sub(make.plan())
    base = score_subscription(db, sub)
    bumped = score_subscription(db, sub, overrides={"failed_payments": 5})

    assert bumped["features"]["failed_payments"] == 5
    assert bumped["risk"] > base["risk"]


def test_none_overrides_are_ignored(db, make):
    sub = make.sub(make.plan())
    base = score_subscription(db, sub)
    same = score_subscription(db, sub, overrides={"failed_payments": None})

    assert same["risk"] == base["risk"]
    assert same["features"] == base["features"]


def test_reasons_mention_failed_payments(db, make):
    sub = make.sub(make.plan())
    r = score_subscription(db, sub, overrides={"failed_payments": 6})
    assert any("failed payment" in reason for reason in r["reasons"])


def test_score_output_is_consistent(db, make):
    sub = make.sub(make.plan())
    r = score_subscription(db, sub)

    assert r["subscription_id"] == sub.id
    assert r["risk_percent"] == round(r["risk"] * 100)
    expected = "high" if r["risk"] >= 0.7 else "medium" if r["risk"] >= 0.4 else "low"
    assert r["level"] == expected
    assert len(r["reasons"]) <= 3