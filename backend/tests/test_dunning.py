from datetime import datetime, timedelta

import pytest

from app import models
from app.services import dunning
from app.services.dunning import HARD_DECLINES, MAX_ATTEMPTS, plan_for

NOW = datetime(2026, 3, 10, 12, 0)
T0 = datetime(2026, 1, 1, 12, 0)
GENERIC = "generic_decline"  # deliberately not a hard decline


def failed_invoice(db, make, attempt_no, reason, created_at, invoice_status="failed"):
    sub = make.sub(make.plan())
    inv = make.invoice(sub, status=invoice_status)
    db.add(models.Payment(
        invoice_id=inv.id, amount_cents=inv.amount_cents, status="failed",
        failure_reason=reason, attempt_no=attempt_no, created_at=created_at,
    ))
    db.commit()
    return inv


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(dunning, "utcnow", lambda: NOW)


# ---- plan_for: what should happen next ----

def test_invoice_without_payments_has_no_plan(db, make):
    inv = make.invoice(make.sub(make.plan()), status="failed")
    assert plan_for(inv) is None


@pytest.mark.parametrize("attempt,days", [(1, 1), (2, 3), (3, 5), (4, 7)])
def test_retry_delay_grows_with_each_attempt(db, make, attempt, days):
    inv = failed_invoice(db, make, attempt, GENERIC, T0)
    plan = plan_for(inv)
    assert plan["action"] == "retry"
    assert plan["attempts"] == attempt
    assert plan["retry_at"] == T0 + timedelta(days=days)


@pytest.mark.parametrize("attempt,days", [(1, 3), (2, 3), (3, 5), (4, 7)])
def test_insufficient_funds_waits_at_least_three_days(db, make, attempt, days):
    inv = failed_invoice(db, make, attempt, "insufficient_funds", T0)
    assert plan_for(inv)["retry_at"] == T0 + timedelta(days=days)


def test_gives_up_after_the_last_attempt(db, make):
    inv = failed_invoice(db, make, MAX_ATTEMPTS, GENERIC, T0)
    plan = plan_for(inv)
    assert plan["action"] == "give_up"
    assert plan["retry_at"] is None


@pytest.mark.parametrize("reason", sorted(HARD_DECLINES))
def test_hard_decline_needs_a_new_card(db, make, reason):
    inv = failed_invoice(db, make, 1, reason, T0)
    plan = plan_for(inv)
    assert plan["action"] == "needs_new_card"
    assert plan["retry_at"] is None


# ---- run_dunning: acting on the plan ----

def test_retry_not_due_yet_is_skipped(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, 1, GENERIC, NOW - timedelta(hours=12))
    pay = fake_pay()
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa")

    assert report == [{
        "invoice_id": inv.id,
        "result": "not_due_yet",
        "retry_at": (NOW + timedelta(hours=12)).isoformat(),
    }]
    assert pay.calls == []


def test_due_retry_that_succeeds_is_recovered(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, 1, GENERIC, NOW - timedelta(days=2))
    pay = fake_pay("succeeded", attempt_no=2)
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa")

    assert report == [{"invoice_id": inv.id, "result": "recovered", "attempt_no": 2}]
    assert pay.calls == [inv.id]


def test_due_retry_that_fails_again_is_reported(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, 1, GENERIC, NOW - timedelta(days=2))
    pay = fake_pay("failed", attempt_no=2, reason=GENERIC)
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa")

    assert report == [{
        "invoice_id": inv.id, "result": "retry_failed",
        "attempt_no": 2, "reason": GENERIC,
    }]


def test_force_ignores_the_schedule(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, 1, GENERIC, NOW - timedelta(hours=1))
    pay = fake_pay("succeeded", attempt_no=2)
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa", force=True)

    assert report[0]["result"] == "recovered"
    assert pay.calls == [inv.id]


def test_invoice_past_max_attempts_is_given_up(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, MAX_ATTEMPTS, GENERIC, NOW - timedelta(days=1))
    pay = fake_pay()
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa")

    assert report == [{"invoice_id": inv.id, "result": "gave_up"}]
    assert inv.status == "uncollectible"
    assert inv.subscription.status == "canceled"
    assert pay.calls == []


def test_final_retry_that_fails_gives_up(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, MAX_ATTEMPTS - 1, GENERIC, NOW - timedelta(days=8))
    pay = fake_pay("failed", attempt_no=MAX_ATTEMPTS, reason=GENERIC)
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa")

    assert report[0]["result"] == "gave_up"
    assert inv.status == "uncollectible"
    assert inv.subscription.status == "canceled"


def test_hard_decline_is_never_retried(db, make, clock, fake_pay, monkeypatch):
    inv = failed_invoice(db, make, 1, sorted(HARD_DECLINES)[0], NOW - timedelta(days=30))
    pay = fake_pay()
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    report = dunning.run_dunning(db, "pm_card_visa")

    assert report == [{"invoice_id": inv.id, "result": "needs_new_card"}]
    assert inv.status == "failed"
    assert pay.calls == []


def test_only_failed_invoices_are_considered(db, make, clock, fake_pay, monkeypatch):
    failed_invoice(db, make, 1, GENERIC, NOW - timedelta(days=2), invoice_status="paid")
    pay = fake_pay()
    monkeypatch.setattr(dunning, "pay_invoice", pay)

    assert dunning.run_dunning(db, "pm_card_visa") == []
    assert pay.calls == []