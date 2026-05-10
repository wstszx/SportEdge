import pytest

from sports_edge_scanner.models import (
    CandidateOrder,
    OrderBook,
    OrderBookLevel,
    RiskDecision,
    ShadowFill,
    ShadowOrder,
)


def test_orderbook_best_bid_ask_and_spread():
    book = OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.44, size=100.0)],
        asks=[OrderBookLevel(price=0.46, size=50.0)],
        timestamp="2026-05-10T00:00:00+00:00",
    )

    assert book.best_bid == 0.44
    assert book.best_ask == 0.46
    assert book.spread == pytest.approx(0.02)


def test_candidate_risk_order_and_fill_to_dicts():
    candidate = CandidateOrder(
        market_id="m1",
        market_slug="team-a-win",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=0.47,
        requested_notional=10.0,
        fair_probability=0.55,
        edge=0.08,
        reason="fair probability clears executable price",
    )
    decision = RiskDecision(
        allowed=True,
        reasons=["allowed"],
        requested_notional=10.0,
        approved_notional=8.0,
    )
    order = ShadowOrder(
        order_id="shadow-1",
        market_id="m1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=0.47,
        notional=8.0,
        source_signal_id="signal-1",
    )
    fill = ShadowFill(
        order_id="shadow-1",
        status="partial",
        requested_notional=8.0,
        filled_notional=5.0,
        filled_contracts=10.0,
        average_price=0.5,
        unfilled_notional=3.0,
        slippage=0.03,
        consumed_levels=[{"price": 0.5, "notional": 5.0, "contracts": 10.0}],
    )

    assert candidate.to_dict()["outcome_name"] == "Team A"
    assert decision.to_dict()["approved_notional"] == 8.0
    assert order.to_dict()["order_id"] == "shadow-1"
    assert fill.to_dict()["status"] == "partial"
