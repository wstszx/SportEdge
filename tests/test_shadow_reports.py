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


def test_shadow_report_warns_when_auto_estimates_are_all_unusable():
    report = build_shadow_report(
        [
            {
                "event_type": "model_estimate",
                "usable": False,
                "reasons": ["wide spread"],
            }
        ]
    )

    assert "no usable model estimates" in report["data_quality_warnings"]


def test_shadow_report_includes_readiness_section():
    report = build_shadow_report([])

    assert report["readiness"]["ready"] is False
    assert "insufficient shadow runs" in report["readiness"]["blockers"]
    assert "run_count" in report["readiness"]["metrics"]
    assert "min_run_count" in report["readiness"]["thresholds"]


def test_shadow_report_includes_strategy_diagnostics():
    report = build_shadow_report([])

    assert report["strategy_diagnostics"]["status"] == "collecting_data"
    assert "collect more shadow runs" in report["strategy_diagnostics"]["next_actions"]


def test_shadow_report_includes_strategy_funnel():
    report = build_shadow_report(
        [
            {
                "event_type": "orderbook_snapshot",
                "token_id": "t1",
                "bids": [{"price": 0.50, "size": 100}],
                "asks": [{"price": 0.52, "size": 100}],
            },
            {
                "event_type": "model_estimate",
                "token_id": "t1",
                "market_id": "m1",
                "market_slug": "market-1",
                "outcome_name": "YES",
                "probability": 0.55,
                "usable": True,
            },
        ]
    )

    assert report["strategy_funnel"]["min_edge_sensitivity"][0] == {
        "min_edge": 0.03,
        "candidate_count": 1,
    }
