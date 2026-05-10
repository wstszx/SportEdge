import pytest

from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.shadow_signals import candidate_orders_for_market
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


def make_market():
    return Market(
        id="market-1",
        title="Team A vs Team B",
        slug="team-a-team-b",
        active=True,
        closed=False,
        end_time=None,
        liquidity=5000.0,
        volume=10000.0,
        outcomes=[
            MarketOutcome(name="Team A", price=0.46, token_id="token-a"),
            MarketOutcome(name="Team B", price=0.54, token_id="token-b"),
        ],
        source="polymarket",
    )


def test_candidate_generated_for_non_yes_no_outcome_with_edge():
    market = make_market()
    books = {
        "token-a": OrderBook(
            market_id="market-1",
            token_id="token-a",
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[OrderBookLevel(price=0.47, size=100.0)],
            timestamp="2026-05-10T00:00:00+00:00",
        )
    }
    fair = FairProbabilityBook(tokens={"token-a": 0.55})

    candidates = candidate_orders_for_market(
        market,
        fair,
        books,
        min_edge=0.03,
        default_notional=10.0,
    )

    assert len(candidates) == 1
    assert candidates[0].outcome_name == "Team A"
    assert candidates[0].limit_price == pytest.approx(0.52)
    assert candidates[0].edge == pytest.approx(0.08)


def test_no_candidate_without_token_id_or_book_or_edge():
    market = make_market()
    fair = FairProbabilityBook(markets={"market-1": {"Team A": 0.48}})

    assert candidate_orders_for_market(market, fair, {}, min_edge=0.03) == []
