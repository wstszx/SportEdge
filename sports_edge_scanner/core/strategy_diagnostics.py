from typing import Any

from sports_edge_scanner.core.shadow_readiness import ShadowReadinessConfig


def _number(report: dict[str, Any], key: str) -> float:
    try:
        return float(report.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fill_count(report: dict[str, Any]) -> int:
    fills = report.get("fills") or []
    return len(fills) if isinstance(fills, list) else 0


def _usable_rate(model_estimate_count: int, usable_model_estimate_count: int) -> float:
    if not model_estimate_count:
        return 0.0
    return usable_model_estimate_count / model_estimate_count


def evaluate_strategy_diagnostics(
    report: dict[str, Any],
    readiness_config: ShadowReadinessConfig | None = None,
) -> dict[str, Any]:
    config = readiness_config or ShadowReadinessConfig()
    run_count = int(_number(report, "run_count"))
    model_estimate_count = int(_number(report, "model_estimate_count"))
    usable_model_estimate_count = int(_number(report, "usable_model_estimate_count"))
    candidate_count = int(_number(report, "candidate_count"))
    fill_count = _fill_count(report)
    orderbook_error_count = int(_number(report, "orderbook_error_count"))
    shadow_scan_error_count = int(_number(report, "shadow_scan_error_count"))
    rejected_order_count = int(_number(report, "rejected_order_count"))
    unfilled_notional = _number(report, "simulated_unfilled_notional")
    average_slippage = _number(report, "average_slippage")
    usable_rate = _usable_rate(model_estimate_count, usable_model_estimate_count)

    metrics = {
        "run_count": run_count,
        "model_estimate_count": model_estimate_count,
        "usable_model_estimate_count": usable_model_estimate_count,
        "usable_model_estimate_rate": usable_rate,
        "candidate_count": candidate_count,
        "fill_count": fill_count,
        "orderbook_error_count": orderbook_error_count,
        "shadow_scan_error_count": shadow_scan_error_count,
        "rejected_order_count": rejected_order_count,
        "simulated_unfilled_notional": unfilled_notional,
        "average_slippage": average_slippage,
    }

    issues: list[str] = []
    next_actions: list[str] = []
    execution_quality_problem = (
        orderbook_error_count
        or shadow_scan_error_count
        or rejected_order_count
        or unfilled_notional
        or (fill_count and average_slippage > config.max_average_slippage)
    )
    if execution_quality_problem:
        issues.append("execution data quality issue")
        next_actions.append("fix execution data quality before collecting more samples")
        status = "execution_quality_issue"
    elif run_count < config.min_run_count or model_estimate_count < config.min_model_estimate_count:
        issues.append("insufficient sample size")
        next_actions.append("collect more shadow runs")
        status = "collecting_data"
    elif usable_rate < config.min_usable_estimate_rate:
        issues.append("usable model estimate rate below minimum")
        next_actions.append("improve market filters or model confidence")
        status = "collecting_data"
    elif candidate_count == 0:
        issues.append("conservative auto fair is not producing edge")
        next_actions.append("add independent signal source")
        status = "needs_independent_signal"
    elif fill_count == 0:
        issues.append("candidate signals have not produced simulated fills")
        next_actions.append("continue shadow collection for execution samples")
        status = "needs_execution_samples"
    elif report.get("readiness", {}).get("ready"):
        status = "healthy"
    else:
        issues.append("readiness blockers remain")
        next_actions.append("review readiness blockers")
        status = "needs_execution_samples"

    return {
        "status": status,
        "issues": issues,
        "next_actions": next_actions,
        "metrics": metrics,
    }
