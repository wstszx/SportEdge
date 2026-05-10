import pytest

from sports_edge_scanner.core.auto_fair import (
    AutoFairConfig,
    build_auto_fair_probability_book,
    estimate_fair_probabilities_for_market,
)
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


def market(**overrides):
    values = {
        "id": "m1",
        "title": "Team A vs Team B",
        "slug": "team-a-team-b",
        "active": True,
        "closed": False,
        "end_time": None,
        "liquidity": 5000.0,
        "volume": 10000.0,
        "outcomes": [
            MarketOutcome(name="Team A", price=0.51, token_id="token-a"),
            MarketOutcome(name="Team B", price=0.49, token_id="token-b"),
        ],
        "source": "polymarket",
    }
    values.update(overrides)
    return Market(**values)


def book(token_id="token-a", bid=0.49, ask=0.51, size=100.0):
    return OrderBook(
        market_id="m1",
        token_id=token_id,
        bids=[OrderBookLevel(price=bid, size=size)],
        asks=[OrderBookLevel(price=ask, size=size)],
        timestamp="2026-05-10T00:00:00+00:00",
    )


def test_estimate_uses_orderbook_midpoint_when_available():
    estimates = estimate_fair_probabilities_for_market(
        market(),
        {"token-a": book()},
        AutoFairConfig(min_confidence=0.75),
    )

    estimate = estimates[0]
    assert estimate.probability == pytest.approx(0.50)
    assert estimate.confidence >= 0.75
    assert estimate.source == "orderbook_midpoint"
    assert estimate.usable is True


def test_estimate_falls_back_to_display_price_with_low_confidence():
    estimates = estimate_fair_probabilities_for_market(
        market(),
        {},
        AutoFairConfig(min_confidence=0.75),
    )

    estimate = estimates[0]
    assert estimate.probability == 0.51
    assert estimate.confidence <= 0.55
    assert estimate.usable is False
    assert "display price only" in estimate.reasons


def test_closed_market_estimate_is_unusable():
    estimates = estimate_fair_probabilities_for_market(
        market(active=False, closed=True),
        {"token-a": book()},
        AutoFairConfig(min_confidence=0.75),
    )

    assert estimates[0].usable is False
    assert "market closed or inactive" in estimates[0].reasons


def test_wide_spread_and_low_liquidity_reduce_confidence():
    estimates = estimate_fair_probabilities_for_market(
        market(liquidity=100.0),
        {"token-a": book(bid=0.40, ask=0.60, size=1.0)},
        AutoFairConfig(min_confidence=0.75, min_liquidity=1000.0, max_spread=0.08),
    )

    estimate = estimates[0]
    assert estimate.usable is False
    assert "wide spread" in estimate.reasons
    assert "low liquidity" in estimate.reasons
    assert "thin top of book" in estimate.reasons


def test_auto_fair_book_includes_only_usable_estimates():
    fair_book, estimates = build_auto_fair_probability_book(
        [market()],
        {
            "m1": {
                "token-a": book(),
                "token-b": book(token_id="token-b", bid=0.48, ask=0.50),
            }
        },
        AutoFairConfig(min_confidence=0.75),
    )

    assert fair_book.tokens["token-a"] == pytest.approx(0.50)
    assert fair_book.tokens["token-b"] == pytest.approx(0.49)
    assert len(estimates) == 2
