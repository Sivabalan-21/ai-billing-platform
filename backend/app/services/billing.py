from datetime import datetime, timedelta, timezone

PERIOD_DAYS = {"month": 30, "year": 365}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def period_end(start: datetime, interval: str) -> datetime:
    return start + timedelta(days=PERIOD_DAYS[interval])


def plan_change_amount(sub, old_plan, new_plan, now: datetime):
    """Returns (net_cents, starts_new_period).
    net > 0 -> customer owes this; net < 0 -> customer gets this as credit."""
    total = (sub.current_period_end - sub.current_period_start).total_seconds()
    remaining = max((sub.current_period_end - now).total_seconds(), 0)
    ratio = remaining / total
    credit = round(old_plan.amount_cents * ratio)

    if old_plan.interval == new_plan.interval:
        # same cycle: charge new plan for the remaining days, minus unused old plan
        return round(new_plan.amount_cents * ratio) - credit, False

    # monthly <-> annual: new cycle starts now, full price minus unused credit
    return new_plan.amount_cents - credit, True