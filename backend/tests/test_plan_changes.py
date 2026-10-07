from datetime import datetime

import pytest

from app import models
from app.services import plan_changes, renewals
from app.services.plan_changes import add_interval, apply_change, calculate_change

NOW = datetime(2026, 3, 16, 0, 0)    # halfway through the period below
START = datetime(2026, 3, 1, 0, 0)
END = datetime(2026, 3, 31, 0, 0)    # 30-day period, 15 days left = 0.5


class FrozenDatetime(datetime):
    @classmethod
    def utcnow(cls):
        return NOW


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(plan_changes, "datetime", FrozenDatetime)


def subscription(db, make, plan, start=START, end=END):
    sub = make.sub(plan)
    sub.current_period_start = start
    sub.current_period_end = end
    db.commit()
    return sub


# ---- add_interval ----

@pytest.mark.parametrize("start,interval,expected", [
    (datetime(2026, 1, 15, 9, 30), "month", datetime(2026, 2, 15, 9, 30)),
    (datetime(2026, 1, 31), "month", datetime(2026, 2, 28)),
    (datetime(2024, 1, 31), "month", datetime(2024, 2, 29)),
    (datetime(2026, 12, 15), "month", datetime(2027, 1, 15)),
    (datetime(2026, 3, 16), "year", datetime(2027, 3, 16)),
    (datetime(2024, 2, 29), "year", datetime(2025, 2, 28)),
])
def test_add_interval(start, interval, expected):
    assert add_interval(start, interval) == expected


# ---- calculate_change ----

def test_same_interval_upgrade_is_prorated(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, basic)

    c = calculate_change(db, sub, pro.id)

    assert c["unused_fraction"] == 0.5
    assert c["credit_cents"] == 5000
    assert c["charge_cents"] == 10000
    assert c["net_cents"] == 5000
    assert c["new_period_start"] == START
    assert c["new_period_end"] == END


def test_downgrade_gives_a_credit(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, pro)

    c = calculate_change(db, sub, basic.id)

    assert c["credit_cents"] == 10000
    assert c["charge_cents"] == 5000
    assert c["net_cents"] == -5000


def test_monthly_to_annual_starts_a_new_period(db, make, clock):
    monthly = make.plan(amount=10000, interval="month")
    annual = make.plan(amount=100000, interval="year")
    sub = subscription(db, make, monthly)

    c = calculate_change(db, sub, annual.id)

    assert c["credit_cents"] == 5000
    assert c["charge_cents"] == 100000          # full price, fresh period
    assert c["net_cents"] == 95000
    assert c["new_period_start"] == NOW
    assert c["new_period_end"] == datetime(2027, 3, 16)


def test_same_plan_is_rejected(db, make, clock):
    plan = make.plan()
    with pytest.raises(ValueError, match="already on this plan"):
        calculate_change(db, subscription(db, make, plan), plan.id)


def test_unknown_plan_is_rejected(db, make, clock):
    with pytest.raises(ValueError, match="not found"):
        calculate_change(db, subscription(db, make, make.plan()), 999)


def test_changing_currency_is_rejected(db, make, clock):
    usd, eur = make.plan(currency="usd"), make.plan(currency="eur")
    with pytest.raises(ValueError, match="currency"):
        calculate_change(db, subscription(db, make, usd), eur.id)


def test_expired_period_has_nothing_left_to_credit(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, basic, datetime(2026, 2, 1), datetime(2026, 3, 1))

    c = calculate_change(db, sub, pro.id)

    assert c["unused_fraction"] == 0
    assert c["credit_cents"] == 0
    assert c["charge_cents"] == 0
    assert c["net_cents"] == 0


def test_zero_length_period_does_not_divide_by_zero(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, basic, NOW, NOW)

    c = calculate_change(db, sub, pro.id)

    assert c["unused_fraction"] == 0
    assert c["net_cents"] == 0


def test_period_not_started_yet_is_capped_at_the_full_amount(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, basic, datetime(2026, 4, 1), datetime(2026, 5, 1))

    c = calculate_change(db, sub, pro.id)

    assert c["unused_fraction"] == 1.0
    assert c["credit_cents"] == 10000
    assert c["charge_cents"] == 20000


# ---- apply_change ----
# NOTE: the upgrade tests fail with "NOT NULL constraint failed: invoices.due_date"
# until apply_change() sets a due_date on the invoice it creates.

def test_upgrade_creates_an_open_invoice_and_logs_the_change(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, basic)

    c, invoice = apply_change(db, sub, pro.id)

    assert invoice is not None
    assert invoice.amount_cents == 5000
    assert invoice.status == "open"
    assert invoice.currency == "usd"
    assert invoice.due_date == NOW
    assert db.get(models.Subscription, sub.id).plan_id == pro.id

    change = db.query(models.PlanChange).one()
    assert change.net_cents == 5000
    assert change.credit_cents == 5000
    assert change.charge_cents == 10000
    assert change.invoice_id == invoice.id


def test_downgrade_creates_no_invoice_but_logs_a_credit(db, make, clock):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, pro)

    c, invoice = apply_change(db, sub, basic.id)

    assert invoice is None
    assert db.query(models.Invoice).count() == 0
    assert db.get(models.Subscription, sub.id).plan_id == basic.id
    change = db.query(models.PlanChange).one()
    assert change.net_cents == -5000
    assert change.invoice_id is None


def test_even_swap_creates_no_invoice(db, make, clock):
    a, b = make.plan(amount=10000), make.plan(amount=10000)
    sub = subscription(db, make, a)

    c, invoice = apply_change(db, sub, b.id)

    assert c["net_cents"] == 0
    assert invoice is None
    assert db.get(models.Subscription, sub.id).plan_id == b.id


def test_monthly_to_annual_moves_the_period(db, make, clock):
    monthly = make.plan(amount=10000, interval="month")
    annual = make.plan(amount=100000, interval="year")
    sub = subscription(db, make, monthly)

    apply_change(db, sub, annual.id)

    sub = db.get(models.Subscription, sub.id)
    assert sub.current_period_start == NOW
    assert sub.current_period_end == datetime(2027, 3, 16)


def test_rejected_change_writes_nothing(db, make, clock):
    plan = make.plan()
    sub = subscription(db, make, plan)

    with pytest.raises(ValueError):
        apply_change(db, sub, plan.id)

    assert db.query(models.PlanChange).count() == 0
    assert db.query(models.Invoice).count() == 0
    assert db.get(models.Subscription, sub.id).plan_id == plan.id


def test_downgrade_credit_is_used_on_the_next_renewal(db, make, fake_pay, clock, monkeypatch):
    basic, pro = make.plan(amount=10000), make.plan(amount=20000)
    sub = subscription(db, make, pro)
    apply_change(db, sub, basic.id)          # credit of 5000

    monkeypatch.setattr(renewals, "pay_invoice", fake_pay())
    report = renewals.renew_due(db, "pm_card_visa", subscription_id=sub.id, force=True)

    assert report[0]["result"] == "succeeded", report
    assert report[0]["amount_cents"] == 5000            # 10000 basic price - 5000 credit
    assert report[0]["credit_applied_cents"] == 5000    