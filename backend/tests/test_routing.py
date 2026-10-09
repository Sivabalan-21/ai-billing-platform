import re

from fastapi.routing import APIRoute
from starlette.routing import Match

from app.main import app


def child_routes(route):
    inner = getattr(route, "original_router", None)
    if inner is not None:
        return inner.routes
    return getattr(route, "routes", None)


def handler_for(method, path):
    """Return the endpoint FastAPI would call for a matching route."""

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
    }

    def find_route(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                match, _ = route.matches(scope)

                if match == Match.FULL:
                    return route.endpoint

            elif child_routes(route):
                result = find_route(child_routes(route))

                if result is not None:
                    return result

        return None

    return find_route(app.routes)


def test_change_plan_is_served_by_the_tested_router():
    handler = handler_for("POST", "/subscriptions/1/change-plan")

    assert handler is not None
    assert handler.__module__ == "app.routers.plan_changes"


def test_change_plan_preview_exists():
    handler = handler_for("GET", "/subscriptions/1/change-plan/preview")

    assert handler is not None


def test_no_route_is_registered_twice():
    matches = []

    def collect_routes(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                if (
                    re.sub(r"\{[^}]+\}", "{}", route.path)
                    == "/subscriptions/{}/change-plan"
                    and "POST" in route.methods
                ):
                    matches.append(route)

            elif child_routes(route):
                collect_routes(child_routes(route))

    collect_routes(app.routes)

    assert len(matches) == 1, (
        "the old change-plan route in routers/billing.py is still registered"
    )