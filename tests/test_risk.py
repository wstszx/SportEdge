from sports_edge_scanner.core.risk import RiskConfig, evaluate_candidate_order
from sports_edge_scanner.models import ShadowFill
from sports_edge_scanner.models import CandidateOrder, OrderBook, OrderBookLevel


def make_candidate():
    return CandidateOrder(
        market_id="m1",
        market_slug="m1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=0.47,
        requested_notional=10.0,
        fair_probability=0.55,
        edge=0.08,
        reason="edge",
    )


def make_book():
    return OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.45, size=100.0)],
        asks=[OrderBookLevel(price=0.47, size=100.0)],
        timestamp="2026-05-10T00:00:00+00:00",
    )


def test_risk_allows_candidate_within_limits():
    decision = evaluate_candidate_order(
        make_candidate(),
        make_book(),
        RiskConfig(),
        market_exposure=0.0,
        total_exposure=0.0,
        daily_pnl=0.0,
    )

    assert decision.allowed is True
    assert decision.approved_notional == 10.0


def test_risk_reduces_to_order_and_market_limits():
    config = RiskConfig(max_order_notional=8.0, max_market_exposure=12.0)

    decision = evaluate_candidate_order(
        make_candidate(),
        make_book(),
        config,
        market_exposure=6.0,
        total_exposure=0.0,
        daily_pnl=0.0,
    )

    assert decision.allowed is True
    assert decision.approved_notional == 6.0
    assert "reduced for max_market_exposure" in decision.reasons


def test_risk_rejects_wide_spread_and_daily_loss():
    config = RiskConfig(max_spread=0.01, daily_loss_limit=5.0)
    book = OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.40, size=100.0)],
        asks=[OrderBookLevel(price=0.47, size=100.0)],
        timestamp="2026-05-10T00:00:00+00:00",
    )

    decision = evaluate_candidate_order(
        make_candidate(),
        book,
        config,
        market_exposure=0.0,
        total_exposure=0.0,
        daily_pnl=-5.0,
    )

    assert decision.allowed is False
    assert "wide spread" in decision.reasons
    assert "daily loss limit reached" in decision.reasons


def test_risk_rejects_low_liquidity_market():
    candidate = make_candidate()

    decision = evaluate_candidate_order(
        candidate,
        make_book(),
        RiskConfig(min_liquidity=1000.0),
        market_exposure=0.0,
        total_exposure=0.0,
        daily_pnl=0.0,
        market_liquidity=500.0,
    )

    assert decision.allowed is False
    assert "low liquidity" in decision.reasons


def test_risk_rejects_stale_books_and_excessive_slippage():
    fill = ShadowFill(
        order_id="shadow-1",
        status="full",
        requested_notional=10.0,
        filled_notional=10.0,
        filled_contracts=20.0,
        average_price=0.50,
        unfilled_notional=0.0,
        slippage=0.03,
        consumed_levels=[],
    )

    decision = evaluate_candidate_order(
        make_candidate(),
        make_book(),
        RiskConfig(max_slippage=0.02, stale_book_seconds=30),
        market_exposure=0.0,
        total_exposure=0.0,
        daily_pnl=0.0,
        orderbook_age_seconds=31.0,
        simulated_fill=fill,
    )

    assert decision.allowed is False
    assert "stale orderbook" in decision.reasons
    assert "slippage above maximum" in decision.reasons
