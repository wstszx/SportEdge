import pytest

from sports_edge_scanner.core.pricing import (
    break_even_probability,
    expected_value_per_unit,
    implied_probability,
    validate_price,
)


def test_implied_probability_matches_market_price():
    assert implied_probability(0.47) == pytest.approx(0.47)


def test_break_even_probability_includes_cost_buffer():
    assert break_even_probability(0.47, cost_buffer=0.01) == pytest.approx(0.48)


def test_expected_value_per_unit_uses_net_payout_after_price_and_cost():
    assert expected_value_per_unit(0.55, 0.47, cost_buffer=0.01) == pytest.approx(0.07)


@pytest.mark.parametrize("price", [0.0, 1.0, -0.1, 1.1])
def test_validate_price_rejects_prices_outside_open_interval(price):
    with pytest.raises(ValueError):
        validate_price(price)
