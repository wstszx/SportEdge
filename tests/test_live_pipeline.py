from datetime import datetime, timezone

from sports_edge_scanner.core.events import read_events
from sports_edge_scanner.core.execution import (
    ExecutionResult,
    LiveModeConfig,
    run_live_scan,
)
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig
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


class RecordingExecutionClient:
    def __init__(self):
        self.orders = []

    def place_order(self, order):
        self.orders.append(order)
        return ExecutionResult(
            client_order_id=order.client_order_id,
            venue_order_id=f"venue-{len(self.orders)}",
            status="submitted",
            filled_notional=0.0,
            remaining_notional=order.notional,
            average_price=None,
            message="submitted",
            raw={"sdk_status": "submitted"},
        )

    def cancel_order(self, order_id):
        raise AssertionError("cancel_order should not be called")

    def get_order(self, order_id):
        raise AssertionError("get_order should not be called")


class RejectingExecutionClient(RecordingExecutionClient):
    def place_order(self, order):
        self.orders.append(order)
        return ExecutionResult(
            client_order_id=order.client_order_id,
            venue_order_id="",
            status="sdk_error",
            filled_notional=0.0,
            remaining_notional=order.notional,
            average_price=None,
            message="sdk_error",
            raw={},
        )


def test_run_live_scan_uses_shadow_signal_and_risk_flow_then_places_real_order(tmp_path):
    execution_client = RecordingExecutionClient()

    summary = run_live_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55}),
        risk_config=RiskConfig(max_order_notional=10.0),
        live_config=LiveModeConfig(
            mode="live",
            live_enabled=True,
            kill_switch_enabled=False,
            require_confirmation_token=False,
        ),
        execution_client=execution_client,
        limit=1,
        events_path=tmp_path / "execution_events.jsonl",
        run_id="run-1",
        now=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )

    events = read_events(tmp_path / "execution_events.jsonl")

    assert summary["candidate_count"] == 1
    assert summary["accepted_order_count"] == 1
    assert summary["execution_submitted_count"] == 1
    assert execution_client.orders[0].market_id == "market-1"
    assert execution_client.orders[0].token_id == "token-a"
    assert execution_client.orders[0].limit_price == 0.52
    assert execution_client.orders[0].notional == 10.0
    assert [event["event_type"] for event in events] == [
        "orderbook_snapshot",
        "orderbook_snapshot",
        "signal",
        "risk_decision",
        "execution_intent",
        "live_guard_decision",
        "execution_order",
        "execution_result",
    ]


def test_run_live_scan_rejects_when_live_guard_blocks_order(tmp_path):
    execution_client = RecordingExecutionClient()

    summary = run_live_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55}),
        risk_config=RiskConfig(max_order_notional=10.0),
        live_config=LiveModeConfig(mode="live", live_enabled=True),
        execution_client=execution_client,
        limit=1,
        events_path=tmp_path / "execution_events.jsonl",
        run_id="run-1",
        now=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )

    events = read_events(tmp_path / "execution_events.jsonl")

    assert summary["accepted_order_count"] == 0
    assert summary["execution_rejected_count"] == 1
    assert execution_client.orders == []
    assert "execution_rejected" in [event["event_type"] for event in events]
    assert "kill switch enabled" in events[-1]["message"]


def test_run_live_scan_counts_execution_client_failures_as_rejections(tmp_path):
    execution_client = RejectingExecutionClient()

    summary = run_live_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55}),
        risk_config=RiskConfig(max_order_notional=10.0),
        live_config=LiveModeConfig(
            mode="live",
            live_enabled=True,
            kill_switch_enabled=False,
            require_confirmation_token=False,
        ),
        execution_client=execution_client,
        limit=1,
        events_path=tmp_path / "execution_events.jsonl",
        run_id="run-1",
        now=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )

    assert summary["accepted_order_count"] == 0
    assert summary["execution_submitted_count"] == 0
    assert summary["execution_rejected_count"] == 1
    assert execution_client.orders[0].client_order_id == "run-1-live-1"


def test_run_live_scan_returns_zero_execution_counts_without_candidates(tmp_path):
    summary = run_live_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.48}),
        risk_config=RiskConfig(max_order_notional=10.0),
        live_config=LiveModeConfig(
            mode="live",
            live_enabled=True,
            kill_switch_enabled=False,
            require_confirmation_token=False,
        ),
        execution_client=RecordingExecutionClient(),
        limit=1,
        events_path=tmp_path / "execution_events.jsonl",
        run_id="run-1",
        now=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )

    assert summary["candidate_count"] == 0
    assert summary["execution_submitted_count"] == 0
    assert summary["execution_rejected_count"] == 0
