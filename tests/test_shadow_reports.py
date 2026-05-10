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


def test_shadow_report_includes_state_and_data_quality_warnings():
    events = [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {"event_type": "orderbook_error", "market_id": "m2", "token_id": "t2"},
        {"event_type": "risk_decision", "allowed": False, "reasons": ["wide spread"]},
        {
            "event_type": "shadow_fill",
            "market_id": "m1",
            "outcome_name": "Team A",
            "status": "partial",
            "filled_notional": 5.0,
            "unfilled_notional": 3.0,
            "slippage": 0.02,
        },
    ]

    report = build_shadow_report(events)

    assert report["orderbook_error_count"] == 1
    assert report["simulated_unfilled_notional"] == 3.0
    assert report["exposure_by_market"] == {"m1": 5.0}
    assert report["exposure_by_outcome"] == {"m1:Team A": 5.0}
    assert "orderbook errors present" in report["data_quality_warnings"]
    assert "rejected orders present" in report["data_quality_warnings"]
    assert "unfilled shadow orders present" in report["data_quality_warnings"]


def test_shadow_report_counts_model_estimates_and_reasons():
    report = build_shadow_report(
        [
            {
                "event_type": "model_estimate",
                "usable": False,
                "reasons": ["display price only", "low liquidity"],
            },
            {
                "event_type": "model_estimate",
                "usable": True,
                "reasons": ["usable automatic estimate"],
            },
        ]
    )

    assert report["model_estimate_count"] == 2
    assert report["usable_model_estimate_count"] == 1
    assert report["unusable_model_estimate_count"] == 1
    assert report["model_rejections_by_reason"]["display price only"] == 1
    assert report["model_rejections_by_reason"]["low liquidity"] == 1
