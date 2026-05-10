import json
from datetime import datetime, timezone

from sports_edge_scanner.cli import build_parser
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig
from sports_edge_scanner.core.shadow_pipeline import run_shadow_scan
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


class FakeMarketClient:
    def fetch_markets(self, limit):
        return [
            Market(
                id="m1",
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
        ]


class FakeBookClient:
    def fetch_orderbook(self, token_id):
        return OrderBook(
            market_id="m1",
            token_id=token_id,
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[OrderBookLevel(price=0.47, size=100.0)],
            timestamp="2026-05-10T00:00:00+00:00",
        )


class SlippyBookClient:
    def fetch_orderbook(self, token_id):
        return OrderBook(
            market_id="m1",
            token_id=token_id,
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[
                OrderBookLevel(price=0.47, size=1.0),
                OrderBookLevel(price=0.50, size=100.0),
            ],
            timestamp="2026-05-10T00:00:00+00:00",
        )


def test_parser_supports_shadow_scan_and_report():
    parser = build_parser()

    scan_args = parser.parse_args(["shadow", "scan", "--limit", "5"])
    report_args = parser.parse_args(["shadow", "report", "--events", "shadow.jsonl"])

    assert scan_args.command == "shadow"
    assert scan_args.shadow_command == "scan"
    assert report_args.shadow_command == "report"


def test_parser_supports_shadow_init_config():
    parser = build_parser()

    args = parser.parse_args(
        [
            "shadow",
            "init-config",
            "--config",
            "custom_config.json",
            "--fair",
            "custom_fair.json",
            "--force",
        ]
    )

    assert args.command == "shadow"
    assert args.shadow_command == "init-config"
    assert args.config == "custom_config.json"
    assert args.fair == "custom_fair.json"
    assert args.force is True


def test_run_shadow_scan_writes_signal_risk_order_and_fill_events(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"

    summary = run_shadow_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55}),
        risk_config=RiskConfig(),
        limit=5,
        events_path=events_path,
        run_id="run-1",
        now=datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc),
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    event_types = [event["event_type"] for event in events]

    assert summary["candidate_count"] == 1
    assert "signal" in event_types
    assert "risk_decision" in event_types
    assert "shadow_order" in event_types
    assert "shadow_fill" in event_types


def test_run_shadow_scan_logs_orderbooks_and_tracks_market_exposure(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"

    summary = run_shadow_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55, "token-b": 0.55}),
        risk_config=RiskConfig(max_order_notional=10.0, max_market_exposure=15.0),
        limit=5,
        events_path=events_path,
        run_id="run-1",
        now=datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc),
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    orderbook_events = [
        event for event in events if event["event_type"] == "orderbook_snapshot"
    ]
    approved_notionals = [
        event["approved_notional"]
        for event in events
        if event["event_type"] == "risk_decision" and event["allowed"]
    ]

    assert summary["candidate_count"] == 2
    assert len(orderbook_events) == 2
    assert approved_notionals == [10.0, 5.0]


def test_run_shadow_scan_rejects_high_slippage_before_order_event(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"

    summary = run_shadow_scan(
        market_client=FakeMarketClient(),
        book_client=SlippyBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.60}),
        risk_config=RiskConfig(max_order_notional=10.0, max_slippage=0.01),
        limit=5,
        events_path=events_path,
        run_id="run-1",
        now=datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc),
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    event_types = [event["event_type"] for event in events]
    risk_reasons = [
        reason
        for event in events
        if event["event_type"] == "risk_decision"
        for reason in event["reasons"]
    ]

    assert summary["accepted_order_count"] == 0
    assert summary["rejected_order_count"] == 1
    assert "shadow_order" not in event_types
    assert "slippage above maximum" in risk_reasons


class StaleBookClient:
    def fetch_orderbook(self, token_id):
        return OrderBook(
            market_id="m1",
            token_id=token_id,
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[OrderBookLevel(price=0.47, size=100.0)],
            timestamp="2026-05-10T00:00:00+00:00",
        )


def test_run_shadow_scan_rejects_stale_orderbook(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"

    summary = run_shadow_scan(
        market_client=FakeMarketClient(),
        book_client=StaleBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55}),
        risk_config=RiskConfig(stale_book_seconds=30),
        limit=5,
        events_path=events_path,
        run_id="run-1",
        now=datetime(2026, 5, 10, 0, 1, tzinfo=timezone.utc),
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    risk_reasons = [
        reason
        for event in events
        if event["event_type"] == "risk_decision"
        for reason in event["reasons"]
    ]

    assert summary["accepted_order_count"] == 0
    assert summary["rejected_order_count"] == 1
    assert "stale orderbook" in risk_reasons
