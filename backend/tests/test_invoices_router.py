from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.routers import invoices
from app.services import payments
from helpers import FakeProvider

FIXED = datetime(2026, 3, 16, 12, 0)


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(invoices.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def quiet_payments(monkeypatch):
    """No revenue recognition or notifications while testing the pay endpoint."""
    monkeypatch.setattr(payments, "recognize_invoice", lambda db, inv: None)
    monkeypatch.setattr(payments, "notify_payment", lambda db, inv, pay: None)


# ---- GET /invoices ----

def test_invoices_are_listed_newest_first(client, make):
    sub = make.sub(make.plan())
    ids = [make.invoice(sub).id for _ in range(3)]

    r = client.get("/invoices")

    assert r.status_code == 200
    assert [i["id"] for i in r.json()] == sorted(ids, reverse=True)


def test_invoices_can_be_filtered_by_subscription(client, make):
    plan = make.plan()
    sub_a, sub_b = make.sub(plan), make.sub(plan)
    mine = make.invoice(sub_a)
    make.invoice(sub_b)

    r = client.get("/invoices", params={"subscription_id": sub_a.id})

    assert [i["id"] for i in r.json()] == [mine.id]


# ---- POST /invoices/{id}/pay ----

def test_paying_an_unknown_invoice_is_404(client):
    r = client.post("/invoices/999/pay", json={"payment_method": "pm_card_visa"})
    assert r.status_code == 404


def test_paying_a_paid_invoice_is_400(client, make):
    inv = make.invoice(make.sub(make.plan()), status="paid")

    r = client.post(f"/invoices/{inv.id}/pay", json={"payment_method": "pm_card_visa"})

    assert r.status_code == 400
    assert "already paid" in r.json()["detail"]


def test_unknown_provider_is_a_400_not_a_crash(client, make, quiet_payments, monkeypatch):
    def boom(name):
        raise ValueError("Unknown provider")
    monkeypatch.setattr(payments, "get_provider", boom)
    inv = make.invoice(make.sub(make.plan()), status="open")

    r = client.post(
        f"/invoices/{inv.id}/pay",
        json={"payment_method": "pm_card_visa", "provider": "nope"},
    )

    assert r.status_code == 400


def test_successful_payment_through_the_api(client, make, quiet_payments, monkeypatch):
    monkeypatch.setattr(payments, "get_provider", lambda name: FakeProvider(success=True))
    inv = make.invoice(make.sub(make.plan()), status="open")

    r = client.post(f"/invoices/{inv.id}/pay", json={"payment_method": "pm_card_visa"})

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "succeeded"


# ---- POST /billing/run ----

@pytest.fixture
def billing(monkeypatch):
    seen = SimpleNamespace(now=None)

    def fake_generate(db, now):
        seen.now = now
        return [SimpleNamespace(id=7), SimpleNamespace(id=8)]

    monkeypatch.setattr(invoices, "utcnow", lambda: FIXED)
    monkeypatch.setattr(invoices, "generate_due_invoices", fake_generate)
    return seen


def test_billing_run_reports_what_was_created(client, billing):
    r = client.post("/billing/run")

    assert r.status_code == 200
    assert r.json() == {"invoices_created": 2, "invoice_ids": [7, 8]}
    assert billing.now == FIXED


def test_days_ahead_moves_the_clock_forward(client, billing):
    client.post("/billing/run", params={"days_ahead": 3})
    assert billing.now == FIXED + timedelta(days=3)