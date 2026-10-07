import app.services.pricing as pricing
from app.config import settings
from app.services.pricing import analyze_plan, pricing_suggestions


def test_few_customers_means_insufficient_data(db, make):
    plan = make.plan()
    make.sub(plan)
    make.sub(plan)

    r = analyze_plan(db, plan, min_subs=3)
    assert r["customers"] == 2
    assert r["action"] == "insufficient_data"
    assert r["suggested_price_cents"] is None


def test_canceled_subscriptions_are_not_counted(db, make):
    plan = make.plan()
    make.sub(plan, status="canceled")

    r = analyze_plan(db, plan, min_subs=1)
    assert r["customers"] == 0
    assert r["action"] == "insufficient_data"


def test_yearly_plan_revenue_is_monthly(db, make):
    plan = make.plan(amount=120000, interval="year")
    make.sub(plan)
    make.sub(plan)

    r = analyze_plan(db, plan, min_subs=5)
    assert r["monthly_revenue_cents"] == 20000


def test_suggestion_is_consistent_with_its_action(db, make):
    plan = make.plan(amount=9900)
    for _ in range(3):
        make.sub(plan)

    r = analyze_plan(db, plan, min_subs=3)
    assert r["action"] in {"raise_price", "lower_price", "hold"}
    if r["action"] == "hold":
        assert r["change_percent"] == 0
        assert r["suggested_price_cents"] == 9900
    elif r["action"] == "raise_price":
        assert r["change_percent"] > 0
        assert r["suggested_price_cents"] > 9900
    else:
        assert r["change_percent"] < 0
        assert r["suggested_price_cents"] < 9900


def test_revenue_shares_add_up_and_are_ranked(db, make):
    big = make.plan(amount=20000)
    small = make.plan(amount=5000)
    make.sub(big)
    make.sub(small)

    out = pricing_suggestions(db, min_subs=1)
    shares = [p["share_of_revenue_percent"] for p in out["plans"]]
    assert 98 <= sum(shares) <= 102
    assert out["plans"][0]["plan_id"] == big.id
    assert "assum" in out["assumption"].lower()


def test_explanation_falls_back_to_template_without_a_key(db, make, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    make.sub(make.plan())

    text, source = pricing.explain(pricing_suggestions(db, min_subs=1))
    assert source == "template"
    assert text.strip()