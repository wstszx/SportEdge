import pytest

from sports_edge_scanner.core.shadow_execution import simulate_buy_limit_fill
from sports_edge_scanner.models import OrderBook, OrderBookLevel, ShadowOrder


def make_order(notional=10.0, limit_price=0.50):
    return ShadowOrder(
        order_id="shadow-1",
        market_id="m1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=limit_price,
        notional=notional,
        source_signal_id="signal-1",
    )


def make_book():
    return OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.44, size=100.0)],
        asks=[
            OrderBookLevel(price=0.47, size=10.0),
            OrderBookLevel(price=0.49, size=10.0),
            OrderBookLevel(price=0.52, size=10.0),
        ],
        timestamp="2026-05-10T00:00:00+00:00",
    )


def test_full_fill_walks_asks_up_to_limit():
    fill = simulate_buy_limit_fill(make_order(notional=8.0, limit_price=0.50), make_book())

    assert fill.status == "full"
    assert fill.filled_notional == pytest.approx(8.0)
    assert fill.unfilled_notional == pytest.approx(0.0)
    assert fill.average_price == pytest.approx(0.4780487805)


def test_partial_fill_stops_at_limit_price():
    fill = simulate_buy_limit_fill(make_order(notional=12.0, limit_price=0.48), make_book())

    assert fill.status == "partial"
    assert fill.filled_notional == pytest.approx(4.7)
    assert fill.unfilled_notional == pytest.approx(7.3)


def test_unfilled_when_no_ask_is_at_or_below_limit():
    fill = simulate_buy_limit_fill(make_order(notional=10.0, limit_price=0.46), make_book())

    assert fill.status == "unfilled"
    assert fill.average_price is None
    assert fill.filled_notional == 0.0
