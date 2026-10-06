from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.services.churn import score_subscription
from app.services.emails import send_email

COOLDOWN_DAYS = 30


def discount_for(risk: float) -> int:
    return 20 if risk >= 0.7 else 15 if risk >= 0.5 else 10


def _template(name: str, discount: int) -> tuple[str, str]:
    return (
        f"A {discount}% thank-you from us",
        f"Hi {name},\n\nWe'd love to keep you with us. As a thank-you, we're offering "
        f"{discount}% off your next renewal. Just reply to this email and we'll set it up.\n\n"
        f"The Billing Team\n",
    )


def compose_offer(name: str, discount: int, reasons: list[str]) -> tuple[str, str, str]:
    """Returns (subject, body, source). Uses Claude if a key is set, else a template."""
    if settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            prompt = (
                f"Write a short, warm retention email (under 110 words) from a billing team to "
                f"{name}. Offer {discount}% off their next renewal; they claim it by replying "
                f"to the email. Context about the customer (mention it only gently, if at all): "
                f"{', '.join(reasons) or 'none'}. Do not mention risk scores, AI or tracking. "
                f"Do not invent features, prices or dates. Format: first line 'Subject: <subject>', "
                f"then a blank line, then the body. Sign off 'The Billing Team'."
            )
            msg = client.messages.create(
                model=settings.anthropic_model, max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            first, _, rest = text.partition("\n")
            if first.lower().startswith("subject:") and rest.strip():
                return first.split(":", 1)[1].strip(), rest.strip() + "\n", "claude"
        except Exception:
            pass  # fall through to the template
    subject, body = _template(name, discount)
    return subject, body, "template"


def send_offers(db: Session, min_risk: float, dry_run: bool) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=COOLDOWN_DAYS)
    subs = (db.query(models.Subscription)
            .filter(models.Subscription.status.in_(["active", "past_due"])).all())
    report = []
    for sub in subs:
        s = score_subscription(db, sub)
        if s["risk"] < min_risk:
            continue
        recent = (db.query(models.RetentionOffer)
                  .filter(models.RetentionOffer.subscription_id == sub.id,
                          models.RetentionOffer.created_at >= cutoff).first())
        if recent:
            report.append({"subscription_id": sub.id, "result": "already_offered_recently"})
            continue

        discount = discount_for(s["risk"])
        customer = sub.customer
        subject, body, source = compose_offer(customer.name, discount, s["reasons"])
        item = {"subscription_id": sub.id, "risk_percent": s["risk_percent"],
                "discount_percent": discount, "to": customer.email,
                "subject": subject, "body": body, "source": source}

        if dry_run:
            item["result"] = "preview_only"
        else:
            send_email(db, customer.email, subject, body)
            db.add(models.RetentionOffer(subscription_id=sub.id, risk_percent=s["risk_percent"],
                                         discount_percent=discount, subject=subject, source=source))
            db.commit()
            item["result"] = "sent"
        report.append(item)
    return report