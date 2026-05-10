from sports_edge_scanner.core.shadow_readiness import (
    ShadowReadinessConfig,
    evaluate_shadow_readiness,
)


def clean_report(**overrides):
    report = {
        "run_count": 20,
        "model_estimate_count": 200,
        "usable_model_estimate_count": 120,
        "fills": [{"status": "full"} for _ in range(20)],
        "orderbook_error_count": 0,
        "rejected_order_count": 0,
        "simulated_unfilled_notional": 0.0,
        "average_slippage": 0.01,
        "data_quality_warnings": [],
    }
    report.update(overrides)
    return report


def test_empty_shadow_report_is_not_ready():
    readiness = evaluate_shadow_readiness({})

    assert readiness["ready"] is False
    assert "insufficient shadow runs" in readiness["blockers"]
    assert "insufficient model estimates" in readiness["blockers"]
    assert "insufficient fills" in readiness["blockers"]


def test_clean_shadow_report_can_be_ready():
    readiness = evaluate_shadow_readiness(clean_report())

    assert readiness["ready"] is True
    assert readiness["blockers"] == []
    assert readiness["metrics"]["usable_model_estimate_rate"] == 0.6


def test_low_usable_model_estimate_rate_blocks_readiness():
    readiness = evaluate_shadow_readiness(
        clean_report(usable_model_estimate_count=40)
    )

    assert readiness["ready"] is False
    assert "usable model estimate rate below minimum" in readiness["blockers"]


def test_execution_quality_problems_block_readiness():
    readiness = evaluate_shadow_readiness(
        clean_report(
            orderbook_error_count=1,
            rejected_order_count=1,
            simulated_unfilled_notional=1.0,
            average_slippage=0.03,
        )
    )

    assert readiness["ready"] is False
    assert "orderbook errors present" in readiness["blockers"]
    assert "rejected orders present" in readiness["blockers"]
    assert "unfilled notional present" in readiness["blockers"]
    assert "average slippage above maximum" in readiness["blockers"]


def test_readiness_uses_custom_thresholds():
    readiness = evaluate_shadow_readiness(
        clean_report(run_count=1, model_estimate_count=2, fills=[]),
        ShadowReadinessConfig(
            min_run_count=1,
            min_model_estimate_count=2,
            min_fill_count=0,
        ),
    )

    assert readiness["ready"] is True
    assert readiness["thresholds"]["min_run_count"] == 1
