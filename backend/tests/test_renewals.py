from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.services import renewals


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def renew(db, fake_pay, monkeypatch, status="succeeded", **kwargs):
    pay = fake_pay(status)
    monkeypatch.setattr(renewals, "pay_invoice", pay)
    return renewals.renew_due(db, "pm_card_visa", **kwargs), pay


def add_credit(db, sub, plan, cents):
    db.add(models.PlanChange(
        subscription_id=sub.id, from_plan_id=plan.id, to_plan_id=plan.id,
        credit_cents=cents, charge_cents=0, net_cents=-cents,
    ))
    db.commit()


# NOTE: if these fail with "NOT NULL constraint failed: invoices.due_date",
# renew_due() creates invoices without a due date. See the fix in the notes.

def test_due_subscription_is_invoiced_at_plan_price(db, make, fake_pay, monkeypatch):
    sub = make.sub(make.plan(amount=9900), days_to_renewal=-1)

    report, pay = renew(db, fake_pay, monkeypatch)

    r = report[0]
    assert r["result"] == "succeeded", report
    assert r["amount_cents"] == 9900
    assert r["credit_applied_cents"] == 0
    invoice = db.get(models.Invoice, r["invoice_id"])
    assert invoice.subscription_id == sub.id
    assert invoice.amount_cents == 9900
    assert invoice.status == "open"
    assert pay.calls == [invoice.id]


def test_subscription_not_yet_due_is_left_alone(db, make, fake_pay, monkeypatch):
    make.sub(make.plan(), days_to_renewal=5)
    report, pay = renew(db, fake_pay, monkeypatch)
    assert report == []
    assert pay.calls == []


@pytest.mark.parametrize("status", ["canceled", "past_due", "trialing"])
def test_only_active_subscriptions_renew(db, make, fake_pay, monkeypatch, status):
    make.sub(make.plan(), status=status, days_to_renewal=-1)
    report, _ = renew(db, fake_pay, monkeypatch)
    assert report == []


def test_monthly_period_moves_forward(db, make, fake_pay, monkeypatch):
    sub = make.sub(make.plan(interval="month"), days_to_renewal=-1)
    old_end = sub.current_period_end

    report, _ = renew(db, fake_pay, monkeypatch)
    assert report[0]["result"] == "succeeded", report

    sub = db.get(models.Subscription, sub.id)
    assert sub.current_period_start == old_end
    assert 28 <= (sub.current_period_end - sub.current_period_start).days <= 31


def test_yearly_period_moves_forward(db, make, fake_pay, monkeypatch):
    sub = make.sub(make.plan(amount=120000, interval="year"), days_to_renewal=-1)

    report, _ = renew(db, fake_pay, monkeypatch)
    assert report[0]["result"] == "succeeded", report
    assert report[0]["amount_cents"] == 120000

    sub = db.get(models.Subscription, sub.id)
    assert 360 <= (sub.current_period_end - sub.current_period_start).days <= 366


def test_force_renews_one_subscription_early(db, make, fake_pay, monkeypatch):
    plan = make.plan()
    target = make.sub(plan, days_to_renewal=20)
    make.sub(plan, days_to_renewal=20)

    report, _ = renew(db, fake_pay, monkeypatch, subscription_id=target.id, force=True)

    assert len(report) == 1
    assert report[0]["subscription_id"] == target.id


def test_stored_credit_reduces_the_invoice(db, make, fake_pay, monkeypatch):
    plan = make.plan(amount=9900)
    sub = make.sub(plan, days_to_renewal=-1)
    add_credit(db, sub, plan, 3000)

    report, _ = renew(db, fake_pay, monkeypatch)

    r = report[0]
    assert r["result"] == "succeeded", report
    assert r["amount_cents"] == 6900
    assert r["credit_applied_cents"] == 3000
    assert db.query(models.CreditApplication).count() == 1


def test_credit_bigger_than_the_price_is_not_applied(db, make, fake_pay, monkeypatch):
    plan = make.plan(amount=9900)
    sub = make.sub(plan, days_to_renewal=-1)
    add_credit(db, sub, plan, 20000)

    report, _ = renew(db, fake_pay, monkeypatch)

    r = report[0]
    assert r["result"] == "succeeded", report
    assert r["amount_cents"] == 9900
    assert r["credit_applied_cents"] == 0
    assert db.query(models.CreditApplication).count() == 0


def test_a_credit_is_only_used_once(db, make, fake_pay, monkeypatch):
    plan = make.plan(amount=9900)
    sub = make.sub(plan, days_to_renewal=-1)
    add_credit(db, sub, plan, 3000)

    first, _ = renew(db, fake_pay, monkeypatch)
    assert first[0]["credit_applied_cents"] == 3000, first

    second, _ = renew(db, fake_pay, monkeypatch, subscription_id=sub.id, force=True)
    assert second[0]["amount_cents"] == 9900
    assert second[0]["credit_applied_cents"] == 0


def test_one_failure_does_not_stop_the_others(db, make, fake_pay, monkeypatch):
    plan = make.plan()
    good = make.sub(plan, days_to_renewal=-1)
    bad = make.sub(plan, days_to_renewal=-1)
    # a trial in a currency the plan has no price for makes this one fail
    db.add(models.Trial(subscription_id=bad.id, trial_end=_now(), currency="eur"))
    db.commit()

    report, _ = renew(db, fake_pay, monkeypatch)

    results = {r["subscription_id"]: r for r in report}
    assert results[bad.id]["result"] == "error"
    assert "no price" in results[bad.id]["reason"]
    assert results[good.id]["result"] == "succeeded", report