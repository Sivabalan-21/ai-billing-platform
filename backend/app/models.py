from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint, Text


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    subscriptions = relationship("Subscription", back_populates="customer")


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    interval: Mapped[str] = mapped_column(String(10), default="month")  # month | year
    trial_days: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # trialing | active | past_due | canceled
    current_period_start: Mapped[datetime] = mapped_column(DateTime)
    current_period_end: Mapped[datetime] = mapped_column(DateTime)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)  # last time they used the service (churn signal)
    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan")
    invoices = relationship("Invoice", back_populates="subscription")


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(20), default="open")  # draft | open | paid | failed
    due_date: Mapped[datetime] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    subscription = relationship("Subscription", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))  # succeeded | failed
    provider: Mapped[str] = mapped_column(String(20), default="stripe")
    provider_ref: Mapped[str | None] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(String(120))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    invoice = relationship("Invoice", back_populates="payments")

class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    event_key = Column(String, unique=True, nullable=True)  # stops double-counting retries
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)  # set once billed
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)) 

class PlanChange(Base):
    __tablename__ = "plan_changes"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    from_plan_id = Column(Integer, nullable=False)
    to_plan_id = Column(Integer, nullable=False)
    credit_cents = Column(Integer, nullable=False)    # unused value of the old plan
    charge_cents = Column(Integer, nullable=False)    # cost of the new plan
    net_cents = Column(Integer, nullable=False)       # charge - credit (negative = customer credit)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class PlanPrice(Base):
    __tablename__ = "plan_prices"
    __table_args__ = (UniqueConstraint("plan_id", "currency"),)

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    currency = Column(String, nullable=False)        # "usd", "eur", "inr"
    amount_cents = Column(Integer, nullable=False)   # smallest unit (cents, paise)


class Trial(Base):
    __tablename__ = "trials"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), unique=True, nullable=False)
    trial_end = Column(DateTime, nullable=False)
    currency = Column(String, nullable=False)
    converted = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class RevenueEntry(Base):
    __tablename__ = "revenue_entries"
    __table_args__ = (UniqueConstraint("invoice_id", "period"),)

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    currency = Column(String, nullable=False)
    period = Column(String, nullable=False)          # "2026-10"
    amount_cents = Column(Integer, nullable=False)

class CreditApplication(Base):
    __tablename__ = "credit_applications"

    id = Column(Integer, primary_key=True)
    plan_change_id = Column(Integer, ForeignKey("plan_changes.id"), unique=True, nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True)
    to_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False)   # logged / sent / failed
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class RetentionOffer(Base):
    __tablename__ = "retention_offers"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    risk_percent = Column(Integer, nullable=False)
    discount_percent = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    source = Column(String, nullable=False)   # "claude" or "template"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))