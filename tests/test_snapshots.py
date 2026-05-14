from sports_edge_scanner.core.snapshots import (
    append_snapshots,
    market_snapshot_record,
    read_snapshots,
    run_snapshot_watch,
)
from sports_edge_scanner.models import Market, MarketOutcome, Signal


def make_market():
    return Market(
        id="market-1",
        title="Will Team A win?",
        slug="team-a-win",
        active=True,
        closed=False,
        end_time="2026-06-01T00:00:00Z",
        liquidity=1500.0,
        volume=3000.0,
        outcomes=[
            MarketOutcome(name="YES", price=0.47, token_id="yes-token"),
            MarketOutcome(name="NO", price=0.52, token_id="no-token"),
        ],
        source="polymarket",
    )


def make_signal():
    return Signal(
        market_id="market-1",
        title="Will Team A win?",
        status="watch",
        reasons=["no fair probability supplied"],
        source="polymarket",
    )


def test_market_snapshot_record_captures_prices_break_even_and_signal_status():
    record = market_snapshot_record(
        make_market(),
        make_signal(),
        timestamp="2026-05-09T00:00:00+00:00",
    )

    assert record["timestamp"] == "2026-05-09T00:00:00+00:00"
    assert record["market_id"] == "market-1"
    assert record["slug"] == "team-a-win"
    assert record["yes_price"] == 0.47
    assert record["no_price"] == 0.52
    assert record["yes_break_even"] == 0.47
    assert record["no_break_even"] == 0.52
    assert record["signal_status"] == "watch"
    assert record["signal_reasons"] == ["no fair probability supplied"]


def test_market_snapshot_record_captures_prices_for_named_binary_outcomes():
    market = Market(
        id="market-2",
        title="Team A vs Team B",
        slug="team-a-vs-team-b",
        active=True,
        closed=False,
        end_time=None,
        liquidity=1500.0,
        volume=3000.0,
        outcomes=[
            MarketOutcome(name="Team A", price=0.46, token_id="team-a-token"),
            MarketOutcome(name="Team B", price=0.54, token_id="team-b-token"),
        ],
        source="polymarket",
    )

    record = market_snapshot_record(
        market,
        make_signal(),
        timestamp="2026-05-09T00:00:00+00:00",
    )

    assert record["yes_outcome_name"] == "Team A"
    assert record["no_outcome_name"] == "Team B"
    assert record["yes_price"] == 0.46
    assert record["no_price"] == 0.54
    assert record["yes_break_even"] == 0.46
    assert record["no_break_even"] == 0.54


def test_append_snapshots_writes_jsonl_and_read_snapshots_loads_it(tmp_path):
    path = tmp_path / "snapshots.jsonl"
    record = market_snapshot_record(
        make_market(),
        make_signal(),
        timestamp="2026-05-09T00:00:00+00:00",
    )

    append_snapshots(path, [record])

    assert read_snapshots(path) == [record]


def test_read_snapshots_returns_empty_list_for_missing_file(tmp_path):
    assert read_snapshots(tmp_path / "missing.jsonl") == []


def test_run_snapshot_watch_collects_requested_iterations_without_sleep_after_last():
    calls = []
    sleeps = []

    def collect_once():
        calls.append("collect")
        return 2

    def sleep(seconds):
        sleeps.append(seconds)

    result = run_snapshot_watch(
        collect_once=collect_once,
        iterations=3,
        interval_seconds=15.0,
        sleep=sleep,
    )

    assert result == [2, 2, 2]
    assert calls == ["collect", "collect", "collect"]
    assert sleeps == [15.0, 15.0]


def test_run_snapshot_watch_rejects_bad_iteration_and_interval_values():
    def collect_once():
        return 0

    try:
        run_snapshot_watch(collect_once, iterations=0, interval_seconds=1.0)
        raised_for_iterations = False
    except ValueError:
        raised_for_iterations = True

    try:
        run_snapshot_watch(collect_once, iterations=1, interval_seconds=-1.0)
        raised_for_interval = False
    except ValueError:
        raised_for_interval = True

    assert raised_for_iterations is True
    assert raised_for_interval is True
