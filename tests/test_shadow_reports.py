import pytest

from sports_edge_scanner.core.shadow_reports import build_shadow_report


def test_shadow_report_counts_orders_fills_and_rejections():
    events = [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {"event_type": "risk_decision", "allowed": False, "reasons": ["wide spread"]},
        {
            "event_type": "risk_decision",
            "allowed": True,
            "reasons": ["allowed"],
            "approved_notional": 10.0,
        },
        {"event_type": "shadow_order", "notional": 10.0, "market_id": "m1"},
        {
            "event_type": "shadow_fill",
            "status": "full",
            "filled_notional": 10.0,
            "slippage": 0.01,
        },
        {
            "event_type": "shadow_fill",
            "status": "partial",
            "filled_notional": 5.0,
            "slippage": 0.02,
        },
    ]

    report = build_shadow_report(events)

    assert report["candidate_count"] == 1
    assert report["accepted_order_count"] == 1
    assert report["rejected_order_count"] == 1
    assert report["rejections_by_reason"] == {"wide spread": 1}
    assert report["fill_status_counts"] == {"full": 1, "partial": 1}
    assert report["simulated_notional_filled"] == 15.0
    assert report["average_slippage"] == pytest.approx(0.015)
