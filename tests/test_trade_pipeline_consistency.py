from datetime import datetime, timezone

from sports_edge_scanner.core.execution import (
    ExecutionResult,
    LiveModeConfig,
    run_live_scan,
)
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig
from sports_edge_scanner.core.shadow_pipeline import run_shadow_scan
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


class FakeMarketClient:
    def fetch_markets(self, limit):
        return [
            Market(
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
        ][:limit]


class FakeBookClient:
    def fetch_orderbook(self, token_id):
        return OrderBook(
            market_id="market-1",
            token_id=token_id,
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[OrderBookLevel(price=0.47, size=100.0)],
            timestamp="2026-05-10T00:00:00+00:00",
        )


class AcceptingExecutionClient:
    def place_order(self, order):
        return ExecutionResult(
            client_order_id=order.client_order_id,
            venue_order_id="venue-1",
            status="submitted",
            filled_notional=0.0,
            remaining_notional=order.notional,
            average_price=None,
            message="submitted",
            raw={},
        )

    def cancel_order(self, order_id):
        raise AssertionError("cancel_order should not be called")

    def get_order(self, order_id):
        raise AssertionError("get_order should not be called")


def test_live_and_paper_share_signal_risk_and_candidate_counts(tmp_path):
    kwargs = {
        "market_client": FakeMarketClient(),
        "book_client": FakeBookClient(),
        "fair_book": FairProbabilityBook(tokens={"token-a": 0.55}),
        "risk_config": RiskConfig(max_order_notional=10.0),
        "limit": 1,
        "run_id": "run-1",
        "now": datetime(2026, 5, 10, tzinfo=timezone.utc),
    }
    paper_summary = run_shadow_scan(
        **kwargs,
        events_path=tmp_path / "shadow_events.jsonl",
    )
    live_summary = run_live_scan(
        **kwargs,
        live_config=LiveModeConfig(
            mode="live",
            live_enabled=True,
            kill_switch_enabled=False,
            require_confirmation_token=False,
        ),
        execution_client=AcceptingExecutionClient(),
        events_path=tmp_path / "execution_events.jsonl",
    )

    for key in [
        "markets",
        "candidate_count",
        "accepted_order_count",
        "rejected_order_count",
        "model_estimate_count",
        "usable_model_estimate_count",
    ]:
        assert live_summary[key] == paper_summary[key]
