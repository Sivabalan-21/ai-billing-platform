from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.services import trials
from app.services.trials import price_for, run_trials, set_price, start_trial, trial_usage


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def customer(db, n=1):
    c = models.Customer(email=f"trial{n}@example.com", name=f"Trial {n}", currency="usd")
    db.add(c)
    db.commit()
    return c


def trialing(db, make, days, n=1):
    plan = make.plan(amount=9900)
    sub, trial = start_trial(db, customer(db, n).id, plan.id, days, "usd")
    return plan, sub, trial


@pytest.fixture
def reminders(monkeypatch):
    sent = []
    monkeypatch.setattr(trials, "send_trial_reminder", lambda db, sub, trial: sent.append(sub.id))
    return sent


# ---- price_for / set_price ----

def test_price_in_the_plans_own_currency(db, make):
    assert price_for(db, make.plan(amount=9900, currency="usd"), "usd") == 9900


def test_currency_match_ignores_case(db, make):
    assert price_for(db, make.plan(amount=9900, currency="usd"), "USD") == 9900


def test_price_in_another_currency_uses_the_price_row(db, make):
    plan = make.plan(amount=9900, currency="usd")
    set_price(db, plan.id, "eur", 8900)
    assert price_for(db, plan, "eur") == 8900


def test_missing_price_raises(db, make):
    with pytest.raises(ValueError, match="no price"):
        price_for(db, make.plan(), "eur")


def test_set_price_updates_instead_of_duplicating(db, make):
    plan = make.plan()
    first = set_price(db, plan.id, "EUR", 8900)
    assert first.currency == "eur"

    set_price(db, plan.id, "eur", 9500)

    assert db.query(models.PlanPrice).count() == 1
    assert price_for(db, plan, "eur") == 9500


def test_set_price_rejects_unknown_plan(db):
    with pytest.raises(ValueError, match="Plan not found"):
        set_price(db, 999, "eur", 100)


# ---- start_trial ----

def test_start_trial_creates_a_trialing_subscription(db, make):
    plan = make.plan()
    sub, trial = start_trial(db, customer(db).id, plan.id, 14, "USD")

    assert sub.status == "trialing"
    assert (sub.current_period_end - sub.current_period_start).days == 14
    assert trial.trial_end == sub.current_period_end
    assert trial.currency == "usd"
    assert trial.converted is False


def test_start_trial_rejects_unknown_plan(db):
    with pytest.raises(ValueError, match="Plan not found"):
        start_trial(db, customer(db).id, 999, 14, "usd")


def test_start_trial_rejects_unknown_customer(db, make):
    with pytest.raises(ValueError, match="Customer not found"):
        start_trial(db, 999, make.plan().id, 14, "usd")


def test_start_trial_needs_a_price_in_that_currency(db, make):
    plan = make.plan(currency="usd")
    with pytest.raises(ValueError, match="no price"):
        start_trial(db, customer(db).id, plan.id, 14, "eur")
    assert db.query(models.Subscription).count() == 0


def test_trial_usage_sums_events(db, make):
    sub = make.sub(make.plan())
    for qty in (5, 7):
        db.add(models.UsageEvent(subscription_id=sub.id, quantity=qty))
    db.commit()
    assert trial_usage(db, sub.id) == 12


# ---- run_trials ----
# NOTE: conversion tests fail with "NOT NULL constraint failed: invoices.due_date"
# if convert_trial() creates invoices without a due date. See the fix in the notes.

def test_ended_trial_converts_and_is_invoiced(db, make, fake_pay, reminders, monkeypatch):
    plan, sub, trial = trialing(db, make, days=-1)
    pay = fake_pay("succeeded")
    monkeypatch.setattr(trials, "pay_invoice", pay)

    report = run_trials(db, "pm_card_visa")

    assert report[0]["result"] == "converted", report
    assert report[0]["subscription_id"] == sub.id
    assert db.get(models.Subscription, sub.id).status == "active"
    assert db.get(models.Trial, trial.id).converted is True
    invoice = db.get(models.Invoice, report[0]["invoice_id"])
    assert invoice.amount_cents == 9900
    assert invoice.status == "open"
    assert pay.calls == [invoice.id]


def test_failed_first_payment_is_reported(db, make, fake_pay, reminders, monkeypatch):
    trialing(db, make, days=-1)
    monkeypatch.setattr(trials, "pay_invoice", fake_pay("failed", reason="insufficient_funds"))

    report = run_trials(db, "pm_card_visa")

    assert report[0]["result"] == "payment_failed", report
    assert report[0]["reason"] == "insufficient_funds"


def test_trial_with_plenty_of_time_left_is_untouched(db, make, fake_pay, reminders, monkeypatch):
    plan, sub, trial = trialing(db, make, days=10)
    pay = fake_pay()
    monkeypatch.setattr(trials, "pay_invoice", pay)

    assert run_trials(db, "pm_card_visa") == []
    assert db.get(models.Subscription, sub.id).status == "trialing"
    assert reminders == []
    assert pay.calls == []


def test_reminder_is_sent_once(db, make, fake_pay, reminders, monkeypatch):
    plan, sub, trial = trialing(db, make, days=2)
    monkeypatch.setattr(trials, "pay_invoice", fake_pay())

    first = run_trials(db, "pm_card_visa")
    assert first[0]["result"] == "reminder_queued"
    assert db.get(models.Trial, trial.id).reminder_sent is True
    assert reminders == [sub.id]

    assert run_trials(db, "pm_card_visa") == []
    assert reminders == [sub.id]


def test_force_converts_a_trial_early(db, make, fake_pay, reminders, monkeypatch):
    trialing(db, make, days=10)
    monkeypatch.setattr(trials, "pay_invoice", fake_pay("succeeded"))

    report = run_trials(db, "pm_card_visa", force=True)

    assert report[0]["result"] == "converted", report


def test_converted_trial_is_not_converted_twice(db, make, fake_pay, reminders, monkeypatch):
    trialing(db, make, days=-1)
    pay = fake_pay("succeeded")
    monkeypatch.setattr(trials, "pay_invoice", pay)

    first = run_trials(db, "pm_card_visa")
    assert first[0]["result"] == "converted", first

    assert run_trials(db, "pm_card_visa") == []
    assert len(pay.calls) == 1


def test_trial_on_a_canceled_subscription_is_skipped(db, make, fake_pay, reminders, monkeypatch):
    plan, sub, trial = trialing(db, make, days=-1)
    sub.status = "canceled"
    db.commit()
    pay = fake_pay()
    monkeypatch.setattr(trials, "pay_invoice", pay)

    assert run_trials(db, "pm_card_visa") == []
    assert pay.calls == []