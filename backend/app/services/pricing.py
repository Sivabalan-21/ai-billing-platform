import json
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.services.churn import score_subscription

CANDIDATES = [-0.10, -0.05, 0.0, 0.05, 0.10]
MIN_GAIN = 0.02          # a change must beat today's revenue by 2% to be suggested
LIVE = ["active", "past_due"]


def _monthly(plan: models.Plan) -> float:
    return plan.amount_cents / 12 if plan.interval == "year" else plan.amount_cents


def sensitivity(avg_risk: float) -> float:
    """ASSUMPTION: riskier customers react more strongly to price changes."""
    return 0.5 + avg_risk * 1.5


def estimate_revenue(mrr: float, change: float, e: float) -> float:
    """Revenue after a price change. Raising prices loses customers; cutting prices keeps/wins some."""
    kept = 1 - e * change if change >= 0 else 1 + e * abs(change)
    return mrr * (1 + change) * max(kept, 0)


def analyze_plan(db: Session, plan: models.Plan, min_subs: int) -> dict:
    subs = (db.query(models.Subscription)
            .filter(models.Subscription.plan_id == plan.id,
                    models.Subscription.status.in_(LIVE)).all())
    n = len(subs)
    risks = [score_subscription(db, s)["risk"] for s in subs]
    avg_risk = sum(risks) / n if n else 0.0

    trials = (db.query(models.Trial)
              .join(models.Subscription, models.Trial.subscription_id == models.Subscription.id)
              .filter(models.Subscription.plan_id == plan.id).all())
    conversion = (sum(1 for t in trials if t.converted) / len(trials)) if trials else None
    switched_away = db.query(models.PlanChange).filter_by(from_plan_id=plan.id).count()

    mrr = _monthly(plan) * n
    item = {
        "plan_id": plan.id,
        "plan_name": getattr(plan, "name", f"Plan {plan.id}"),
        "interval": plan.interval,
        "currency": plan.currency.lower(),
        "current_price_cents": plan.amount_cents,
        "customers": n,
        "monthly_revenue_cents": round(mrr),
        "avg_churn_risk_percent": round(avg_risk * 100),
        "trial_conversion_percent": None if conversion is None else round(conversion * 100),
        "customers_switched_away": switched_away,
    }

    if n < min_subs:
        item.update(action="insufficient_data", suggested_price_cents=None,
                    change_percent=0, expected_revenue_change_percent=0,
                    reasoning=[f"Only {n} customer(s) on this plan, so there isn't enough data to judge."])
        return item

    e = sensitivity(avg_risk)
    base = estimate_revenue(mrr, 0.0, e)
    best = max(CANDIDATES, key=lambda c: estimate_revenue(mrr, c, e))
    gain = estimate_revenue(mrr, best, e) / base - 1 if base else 0
    change = best if gain >= MIN_GAIN else 0.0

    reasoning = [f"Customers on this plan have an average churn risk of {round(avg_risk * 100)}%."]
    if conversion is not None:
        reasoning.append(f"{round(conversion * 100)}% of trials on this plan became paying customers.")
    if switched_away:
        reasoning.append(f"{switched_away} customer(s) have moved off this plan.")
    if conversion is not None and conversion < 0.4 and len(trials) >= 3:
        reasoning.append("Trial conversion is low, so the plan may be hard to justify at this price.")

    action = "raise_price" if change > 0 else "lower_price" if change < 0 else "hold"
    item.update(
        action=action,
        change_percent=round(change * 100),
        suggested_price_cents=round(plan.amount_cents * (1 + change) / 100) * 100 if change else plan.amount_cents,
        expected_revenue_change_percent=round(gain * 100, 1) if change else 0,
        reasoning=reasoning,
    )
    return item


def pricing_suggestions(db: Session, min_subs: int = 3) -> dict:
    plans = [analyze_plan(db, p, min_subs) for p in db.query(models.Plan).all()]
    total = sum(p["monthly_revenue_cents"] for p in plans) or 1
    for p in plans:
        p["share_of_revenue_percent"] = round(p["monthly_revenue_cents"] / total * 100)
    return {
        "plans": sorted(plans, key=lambda p: -p["monthly_revenue_cents"]),
        "assumption": ("Price sensitivity is assumed (0.5 + 1.5 x average churn risk) because there is "
                       "no real price-change history yet. Treat the revenue estimates as rough guidance."),
    }


def _template_explanation(plans: list[dict]) -> str:
    lines = []
    for p in plans:
        if p["action"] == "insufficient_data":
            lines.append(f"{p['plan_name']}: not enough customers yet to judge.")
        elif p["action"] == "hold":
            lines.append(f"{p['plan_name']}: keep the current price.")
        else:
            verb = "raising" if p["action"] == "raise_price" else "lowering"
            lines.append(f"{p['plan_name']}: consider {verb} the price by about {abs(p['change_percent'])}% "
                         f"(estimated revenue change {p['expected_revenue_change_percent']}%).")
    return "\n".join(lines)


def explain(result: dict) -> tuple[str, str]:
    """Returns (text, source). Claude if a key is set, otherwise a plain template."""
    if settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            prompt = (
                "You are advising the owner of a subscription business who is not technical. "
                "Below is a pricing analysis in JSON. Explain in under 150 words what to do with "
                "each plan and why, in plain language. Use only the numbers in the JSON, do not "
                "invent any. Make clear the revenue estimates are rough because they rest on an "
                "assumption. Do not mention JSON, models or scores.\n\n"
                + json.dumps(result, default=str)
            )
            msg = client.messages.create(
                model=settings.anthropic_model, max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            if text:
                return text, "claude"
        except Exception:
            pass  # fall back to the template
    return _template_explanation(result["plans"]),