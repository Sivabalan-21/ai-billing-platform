import smtplib
from email.message import EmailMessage
from sqlalchemy.orm import Session
from app import models
from app.config import settings


def money(cents: int, currency: str) -> str:
    return f"{cents / 100:,.2f} {currency.upper()}"


def send_email(db: Session, to: str, subject: str, body: str) -> None:
    """Send via SMTP if configured, otherwise just log. Never raises."""
    status, error = "logged", None
    if settings.smtp_host:
        try:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = settings.email_from, to, subject
            msg.set_content(body)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.starttls()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
            status = "sent"
        except Exception as e:
            status, error = "failed", str(e)[:200]
    try:
        db.add(models.EmailLog(to_email=to, subject=subject, body=body, status=status, error=error))
        db.commit()
    except Exception:
        db.rollback()


def notify_payment(db: Session, invoice: models.Invoice, payment: models.Payment) -> None:
    try:
        customer = invoice.subscription.customer
        amount = money(invoice.amount_cents, invoice.currency)
        if payment.status == "succeeded":
            send_email(db, customer.email, f"Receipt: {amount} paid",
                       f"Hi {customer.name},\n\nWe received your payment of {amount} "
                       f"for invoice #{invoice.id}. Thank you!\n")
        else:
            send_email(db, customer.email, "Your payment didn't go through",
                       f"Hi {customer.name},\n\nWe couldn't charge {amount} for invoice #{invoice.id}. "
                       f"We'll try again automatically. To avoid any interruption, "
                       f"please update your payment method.\n")
    except Exception:
        db.rollback()


def send_trial_reminder(db: Session, sub: models.Subscription, trial: models.Trial) -> None:
    try:
        customer = sub.customer
        send_email(db, customer.email, "Your free trial ends soon",
                   f"Hi {customer.name},\n\nYour trial ends on {trial.trial_end:%b %d, %Y}. "
                   f"After that your first payment will be charged automatically. "
                   f"Cancel any time before then if it's not for you.\n")
    except Exception:
        db.rollback()