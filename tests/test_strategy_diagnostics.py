from sports_edge_scanner.core.strategy_diagnostics import evaluate_strategy_diagnostics


def report(**overrides):
    value = {
        "run_count": 20,
        "model_estimate_count": 200,
        "usable_model_estimate_count": 120,
        "candidate_count": 1,
        "fills": [{"status": "full"} for _ in range(20)],
        "orderbook_error_count": 0,
        "shadow_scan_error_count": 0,
        "rejected_order_count": 0,
        "simulated_unfilled_notional": 0.0,
        "average_slippage": 0.0,
        "readiness": {"ready": True},
    }
    value.update(overrides)
    return value


def test_collecting_data_when_samples_are_insufficient():
    diagnostics = evaluate_strategy_diagnostics(
        report(run_count=3, model_estimate_count=20, usable_model_estimate_count=10)
    )

    assert diagnostics["status"] == "collecting_data"
    assert "collect more shadow runs" in diagnostics["next_actions"]


def test_needs_independent_signal_when_estimates_are_usable_but_no_candidates():
    diagnostics = evaluate_strategy_diagnostics(
        report(candidate_count=0, fills=[], readiness={"ready": False})
    )

    assert diagnostics["status"] == "needs_independent_signal"
    assert "add independent signal source" in diagnostics["next_actions"]
    assert "conservative auto fair is not producing edge" in diagnostics["issues"]


def test_needs_execution_samples_when_candidates_exist_but_no_fills():
    diagnostics = evaluate_strategy_diagnostics(
        report(candidate_count=3, fills=[], readiness={"ready": False})
    )

    assert diagnostics["status"] == "needs_execution_samples"
    assert "continue shadow collection for execution samples" in diagnostics["next_actions"]


def test_execution_quality_issue_when_errors_are_present():
    diagnostics = evaluate_strategy_diagnostics(
        report(orderbook_error_count=1, readiness={"ready": False})
    )

    assert diagnostics["status"] == "execution_quality_issue"
    assert "fix execution data quality before collecting more samples" in diagnostics["next_actions"]


def test_healthy_when_readiness_is_ready():
    diagnostics = evaluate_strategy_diagnostics(report())

    assert diagnostics["status"] == "healthy"
    assert diagnostics["issues"] == []
