from types import SimpleNamespace

import pytest

from app import models
from app.services import payments
from helpers import FakeProvider


@pytest.fixture
def env(monkeypatch):
    """Replaces provider lookup, revenue recognition and notifications, and records calls."""
    rec = SimpleNamespace(asked=[], recognized=[], notified=[])

    def install(provider):
        def get(name):
            rec.asked.append(name)
            return provider
        monkeypatch.setattr(payments, "get_provider", get)

    monkeypatch.setattr(payments, "recognize_invoice", lambda db, inv: rec.recognized.append(inv.id))
    monkeypatch.setattr(payments, "notify_payment", lambda db, inv, pay: rec.notified.append(pay.status))
    rec.install = install
    return rec


def open_invoice(make):
    sub = make.sub(make.plan())
    return sub, make.invoice(sub, amount=9900, status="open")


def add_payment(db, invoice, attempt_no, provider="stripe", status="failed"):
    db.add(models.Payment(
        invoice_id=invoice.id, amount_cents=invoice.amount_cents, status=status,
        provider=provider, failure_reason="generic_decline", attempt_no=attempt_no,
    ))
    db.commit()


# ---- outcomes ----

def test_successful_payment_marks_the_invoice_paid(db, make, env):
    provider = FakeProvider(success=True)
    env.install(provider)
    sub, inv = open_invoice(make)

    payment = payments.pay_invoice(db, inv, "pm_card_visa")

    assert payment.status == "succeeded"
    assert payment.provider == "stripe"
    assert payment.provider_ref == "ref_ok"
    assert payment.attempt_no == 1
    assert inv.status == "paid"
    assert inv.paid_at is not None
    assert provider.charges == [(9900, "usd", "pm_card_visa")]
    assert env.recognized == [inv.id]
    assert env.notified == ["succeeded"]


def test_failed_payment_marks_invoice_failed_and_subscription_past_due(db, make, env):
    env.install(FakeProvider(success=False, reason="insufficient_funds"))
    sub, inv = open_invoice(make)

    payment = payments.pay_invoice(db, inv, "pm_card_visa")

    assert payment.status == "failed"
    assert payment.failure_reason == "insufficient_funds"
    assert payment.provider_ref is None
    assert inv.status == "failed"
    assert inv.paid_at is None
    assert sub.status == "past_due"
    assert env.recognized == []          # no revenue for a failed charge
    assert env.notified == ["failed"]


def test_successful_retry_brings_a_past_due_subscription_back(db, make, env):
    env.install(FakeProvider(success=True))
    sub, inv = open_invoice(make)
    sub.status = "past_due"
    db.commit()

    payments.pay_invoice(db, inv, "pm_card_visa")

    assert sub.status == "active"


def test_attempt_number_counts_previous_payments(db, make, env):
    env.install(FakeProvider(success=False, reason="generic_decline"))
    sub, inv = open_invoice(make)
    add_payment(db, inv, 1)
    add_payment(db, inv, 2)

    payment = payments.pay_invoice(db, inv, "pm_card_visa")

    assert payment.attempt_no == 3


# ---- which provider is used ----

def test_first_payment_uses_the_default_provider(db, make, env):
    env.install(FakeProvider())
    sub, inv = open_invoice(make)

    payments.pay_invoice(db, inv, "pm_card_visa")

    assert env.asked == [payments.DEFAULT_PROVIDER]


def test_retry_reuses_the_provider_of_the_last_attempt(db, make, env):
    env.install(FakeProvider(name="braintree"))
    sub, inv = open_invoice(make)
    add_payment(db, inv, 1, provider="braintree")

    payments.pay_invoice(db, inv, "pm_card_visa")

    assert env.asked == ["braintree"]


def test_explicit_provider_overrides_the_previous_one(db, make, env):
    env.install(FakeProvider(name="stripe"))
    sub, inv = open_invoice(make)
    add_payment(db, inv, 1, provider="braintree")

    payments.pay_invoice(db, inv, "pm_card_visa", provider_name="stripe")

    assert env.asked == ["stripe"]


def test_unknown_provider_raises_and_records_nothing(db, make, env, monkeypatch):
    def boom(name):
        raise ValueError("Unknown provider")
    monkeypatch.setattr(payments, "get_provider", boom)
    sub, inv = open_invoice(make)

    with pytest.raises(ValueError):
        payments.pay_invoice(db, inv, "pm_card_visa", provider_name="nope")

    assert db.query(models.Payment).count() == 0
    assert inv.status == "open"


# ---- test-mode payment method shim ----

def test_non_stripe_provider_swaps_a_stripe_test_token(db, make, env):
    provider = FakeProvider(name="braintree", test_payment_method="fake-valid-nonce")
    env.install(provider)
    sub, inv = open_invoice(make)

    payments.pay_invoice(db, inv, "pm_card_visa")

    assert provider.charges[0][2] == "fake-valid-nonce"


def test_non_stripe_provider_keeps_a_real_token(db, make, env):
    provider = FakeProvider(name="braintree", test_payment_method="fake-valid-nonce")
    env.install(provider)
    sub, inv = open_invoice(make)

    payments.pay_invoice(db, inv, "tok_real_customer")

    assert provider.charges[0][2] == "tok_real_customer"


def test_stripe_keeps_its_own_token(db, make, env):
    provider = FakeProvider(name="stripe", test_payment_method="should-not-be-used")
    env.install(provider)
    sub, inv = open_invoice(make)

    payments.pay_invoice(db, inv, "pm_card_visa")

    assert provider.charges[0][2] == "pm_card_visa"