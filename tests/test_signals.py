import pytest

from sports_edge_scanner.core.signals import classify_market
from sports_edge_scanner.models import Market, MarketOutcome


def make_market(**overrides):
    values = {
        "id": "m1",
        "title": "Team A vs Team B",
        "slug": "team-a-vs-team-b",
        "active": True,
        "closed": False,
        "end_time": None,
        "liquidity": 5000.0,
        "volume": 10000.0,
        "outcomes": [
            MarketOutcome(name="YES", price=0.47, token_id="yes-token"),
            MarketOutcome(name="NO", price=0.52, token_id="no-token"),
        ],
        "source": "polymarket",
    }
    values.update(overrides)
    return Market(**values)


def test_closed_market_is_skipped():
    signal = classify_market(make_market(closed=True))

    assert signal.status == "skip"
    assert "market is closed" in signal.reasons


def test_missing_prices_are_watch_only():
    market = make_market(outcomes=[MarketOutcome(name="YES", price=None)])

    signal = classify_market(market)

    assert signal.status == "watch"
    assert "missing YES or NO price" in signal.reasons


def test_wide_spread_is_watch_only():
    market = make_market(
        outcomes=[
            MarketOutcome(name="YES", price=0.47),
            MarketOutcome(name="NO", price=0.62),
        ]
    )

    signal = classify_market(market, max_spread=0.08)

    assert signal.status == "watch"
    assert "wide spread" in signal.reasons


def test_low_liquidity_adds_warning_but_keeps_watch_status():
    signal = classify_market(make_market(liquidity=100.0), min_liquidity=1000.0)

    assert signal.status == "watch"
    assert "low liquidity" in signal.reasons


def test_candidate_when_fair_probability_clears_edge_threshold():
    signal = classify_market(
        make_market(),
        fair_probabilities={"YES": 0.55},
        min_edge=0.02,
    )

    assert signal.status == "candidate"
    assert signal.side == "YES"
    assert signal.edge == pytest.approx(0.08)
    assert signal.break_even_probability == pytest.approx(0.47)
    assert signal.kelly_fraction > 0.0


def test_no_candidate_when_edge_is_too_small():
    signal = classify_market(
        make_market(),
        fair_probabilities={"YES": 0.48},
        min_edge=0.02,
    )

    assert signal.status == "watch"
    assert "no supplied fair probability clears edge threshold" in signal.reasons
