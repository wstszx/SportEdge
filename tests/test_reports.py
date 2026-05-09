import pytest

from sports_edge_scanner.core.reports import (
    build_quality_report,
    build_report,
    latest_snapshot_by_market,
)


def test_latest_snapshot_by_market_uses_last_record_per_market_id():
    snapshots = [
        {
            "timestamp": "2026-05-09T00:00:00+00:00",
            "market_id": "m1",
            "yes_price": 0.47,
            "no_price": 0.53,
        },
        {
            "timestamp": "2026-05-09T01:00:00+00:00",
            "market_id": "m1",
            "yes_price": 0.51,
            "no_price": 0.49,
        },
    ]

    latest = latest_snapshot_by_market(snapshots)

    assert latest["m1"]["yes_price"] == 0.51


def test_build_report_summarizes_paper_trades_with_mark_to_market_and_clv():
    records = [
        {
            "timestamp": "2026-05-09T00:00:00+00:00",
            "market": "m1",
            "side": "YES",
            "price": 0.47,
            "size": 100.0,
            "note": "tracking",
            "metadata": {"market_id": "m1"},
        },
        {
            "timestamp": "2026-05-09T00:05:00+00:00",
            "market": "m2",
            "side": "NO",
            "price": 0.60,
            "size": 50.0,
            "note": "tracking",
            "metadata": {"market_id": "m2"},
        },
    ]
    snapshots = [
        {
            "timestamp": "2026-05-09T01:00:00+00:00",
            "market_id": "m1",
            "title": "Market 1",
            "yes_price": 0.52,
            "no_price": 0.48,
        },
        {
            "timestamp": "2026-05-09T01:00:00+00:00",
            "market_id": "m2",
            "title": "Market 2",
            "yes_price": 0.35,
            "no_price": 0.65,
        },
    ]

    report = build_report(records, snapshots)

    assert report["paper_trades"] == 2
    assert report["open_trades_with_marks"] == 2
    assert report["total_staked"] == 150.0
    expected_pnl = ((0.52 - 0.47) * (100.0 / 0.47)) + (
        (0.65 - 0.60) * (50.0 / 0.60)
    )
    assert report["mark_to_market_pnl"] == pytest.approx(expected_pnl)
    assert report["mark_to_market_roi"] == pytest.approx(expected_pnl / 150.0)
    assert report["average_clv"] == pytest.approx(0.05)
    assert report["trades"][0]["clv"] == pytest.approx(0.05)


def test_build_report_includes_realized_metrics_from_settlement_records():
    records = [
        {
            "type": "trade",
            "timestamp": "2026-05-09T00:00:00+00:00",
            "market": "m1",
            "side": "YES",
            "price": 0.50,
            "size": 100.0,
            "note": "tracking",
            "metadata": {"market_id": "m1"},
        },
        {
            "type": "trade",
            "timestamp": "2026-05-09T00:05:00+00:00",
            "market": "m2",
            "side": "NO",
            "price": 0.25,
            "size": 50.0,
            "note": "tracking",
            "metadata": {"market_id": "m2"},
        },
        {
            "type": "settlement",
            "timestamp": "2026-05-10T00:00:00+00:00",
            "market": "m1",
            "market_id": "m1",
            "winning_side": "YES",
            "note": "resolved",
        },
        {
            "type": "settlement",
            "timestamp": "2026-05-10T00:05:00+00:00",
            "market": "m2",
            "market_id": "m2",
            "winning_side": "YES",
            "note": "resolved",
        },
    ]

    report = build_report(records, snapshots=[])

    assert report["paper_trades"] == 2
    assert report["settlements"] == 2
    assert report["settled_trades"] == 2
    assert report["realized_wins"] == 1
    assert report["realized_losses"] == 1
    assert report["realized_pnl"] == pytest.approx(50.0)
    assert report["realized_roi"] == pytest.approx(50.0 / 150.0)
    assert report["win_rate"] == pytest.approx(0.5)
    assert report["max_drawdown"] == pytest.approx(50.0)
    assert report["trades"][0]["settled"] is True
    assert report["trades"][0]["realized_pnl"] == pytest.approx(100.0)
    assert report["trades"][1]["realized_pnl"] == pytest.approx(-50.0)


def test_build_report_handles_empty_inputs():
    report = build_report([], [])

    assert report["paper_trades"] == 0
    assert report["settlements"] == 0
    assert report["total_staked"] == 0.0
    assert report["mark_to_market_roi"] == 0.0
    assert report["realized_roi"] == 0.0
    assert report["trades"] == []


def test_build_quality_report_summarizes_snapshot_coverage_and_missing_trade_matches():
    snapshots = [
        {
            "timestamp": "2026-05-09T00:00:00+00:00",
            "market_id": "m1",
            "title": "Market 1",
            "signal_status": "watch",
            "yes_price": 0.47,
            "no_price": 0.53,
        },
        {
            "timestamp": "2026-05-09T01:30:00+00:00",
            "market_id": "m1",
            "title": "Market 1",
            "signal_status": "candidate",
            "yes_price": 0.51,
            "no_price": 0.49,
        },
        {
            "timestamp": "2026-05-09T00:30:00+00:00",
            "market_id": "m2",
            "title": "Market 2",
            "signal_status": "watch",
            "yes_price": None,
            "no_price": None,
        },
    ]
    paper_records = [
        {"market": "m1", "metadata": {"market_id": "m1"}},
        {"market": "m3", "metadata": {"market_id": "m3"}},
    ]

    report = build_quality_report(paper_records, snapshots)

    assert report["snapshot_count"] == 3
    assert report["market_count"] == 2
    assert report["candidate_snapshot_count"] == 1
    assert report["missing_price_snapshot_count"] == 1
    assert report["paper_trade_count"] == 2
    assert report["paper_trades_missing_snapshots"] == 1
    assert report["snapshot_time_span_hours"] == pytest.approx(1.5)
    assert report["markets"][0]["market_id"] == "m1"
    assert report["markets"][0]["snapshot_count"] == 2
    assert report["markets"][0]["time_span_hours"] == pytest.approx(1.5)


def test_build_quality_report_handles_empty_inputs():
    report = build_quality_report([], [])

    assert report["snapshot_count"] == 0
    assert report["market_count"] == 0
    assert report["snapshot_time_span_hours"] == 0.0
    assert report["markets"] == []
