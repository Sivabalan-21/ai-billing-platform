import pytest

from app.services.pricing import CANDIDATES, estimate_revenue, sensitivity


def test_sensitivity_grows_with_churn_risk():
    assert sensitivity(0.0) == pytest.approx(0.5)
    assert sensitivity(1.0) == pytest.approx(2.0)
    assert sensitivity(0.8) > sensitivity(0.1)


def test_no_price_change_keeps_revenue():
    assert estimate_revenue(100, 0.0, 1.0) == pytest.approx(100)


def test_price_rise_loses_some_customers():
    # +10% price, sensitivity 0.5: keeps 95% of customers
    assert estimate_revenue(100, 0.10, 0.5) == pytest.approx(104.5)


def test_price_cut_wins_some_customers():
    # -10% price, sensitivity 0.5: customers rise to 105%
    assert estimate_revenue(100, -0.10, 0.5) == pytest.approx(94.5)


def test_revenue_never_goes_negative():
    # very high sensitivity would lose more than everyone: floor at zero
    assert estimate_revenue(100, 0.10, 20) == 0


def test_low_sensitivity_favours_raising_price():
    best = max(CANDIDATES, key=lambda c: estimate_revenue(100, c, 0.5))
    assert best == 0.10


def test_high_sensitivity_favours_lowering_price():
    best = max(CANDIDATES, key=lambda c: estimate_revenue(100, c, 2.0))
    assert best == -0.10