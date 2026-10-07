from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class Factory:
    def __init__(self, db):
        self.db = db
        self.n = 0

    def plan(self, amount=9900, interval="month", currency="usd", name=None):
        self.n += 1
        p = models.Plan(
            name=name or f"Plan {self.n}",
            amount_cents=amount,
            currency=currency,
            interval=interval,
        )
        self.db.add(p)
        self.db.commit()
        return p

    def sub(self, plan, status="active", days_to_renewal=20, currency="usd"):
        self.n += 1
        customer = models.Customer(
            email=f"customer{self.n}@example.com",
            name=f"Customer {self.n}",
            currency=currency,
        )
        self.db.add(customer)
        self.db.flush()
        now = _now()
        s = models.Subscription(
            customer_id=customer.id,
            plan_id=plan.id,
            status=status,
            current_period_start=now - timedelta(days=10),
            current_period_end=now + timedelta(days=days_to_renewal),
            last_active_at=now,
        )
        self.db.add(s)
        self.db.commit()
        return s

    def invoice(self, sub, amount=9900, status="paid"):
        inv = models.Invoice(
            subscription_id=sub.id,
            amount_cents=amount,
            currency="usd",
            status=status,
            due_date=_now(),
        )
        self.db.add(inv)
        self.db.commit()
        return inv

    def payment(self, invoice, status, reason=None, attempt_no=1):
        pay = models.Payment(
            invoice_id=invoice.id,
            amount_cents=invoice.amount_cents,
            status=status,
            failure_reason=reason,
            attempt_no=attempt_no,
        )
        self.db.add(pay)
        self.db.commit()
        return pay


@pytest.fixture
def make(db):
    return Factory(db)


@pytest.fixture
def fake_pay():
    """Stand-in for pay_invoice so tests never touch a payment provider."""
    from types import SimpleNamespace

    def build(status="succeeded", attempt_no=1, reason=None):
        def pay(db, invoice, payment_method):
            pay.calls.append(invoice.id)
            return SimpleNamespace(status=status, attempt_no=attempt_no, failure_reason=reason)

        pay.calls = []
        return pay

    return build