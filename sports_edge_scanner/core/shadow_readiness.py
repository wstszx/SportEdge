from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ShadowReadinessConfig:
    min_run_count: int = 20
    min_model_estimate_count: int = 200
    min_usable_estimate_rate: float = 0.5
    min_fill_count: int = 20
    max_orderbook_error_count: int = 0
    max_rejected_order_count: int = 0
    max_unfilled_notional: float = 0.0
    max_average_slippage: float = 0.02


def _number(report: dict[str, Any], key: str) -> float:
    try:
        return float(report.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fill_count(report: dict[str, Any]) -> int:
    fills = report.get("fills") or []
    if isinstance(fills, list):
        return len(fills)
    return 0


def evaluate_shadow_readiness(
    report: dict[str, Any],
    config: ShadowReadinessConfig | None = None,
) -> dict[str, Any]:
    effective_config = config or ShadowReadinessConfig()
    run_count = int(_number(report, "run_count"))
    model_estimate_count = int(_number(report, "model_estimate_count"))
    usable_model_estimate_count = int(_number(report, "usable_model_estimate_count"))
    usable_rate = (
        usable_model_estimate_count / model_estimate_count
        if model_estimate_count
        else 0.0
    )
    fill_count = _fill_count(report)
    orderbook_error_count = int(_number(report, "orderbook_error_count"))
    rejected_order_count = int(_number(report, "rejected_order_count"))
    unfilled_notional = _number(report, "simulated_unfilled_notional")
    average_slippage = _number(report, "average_slippage")

    metrics = {
        "run_count": run_count,
        "model_estimate_count": model_estimate_count,
        "usable_model_estimate_count": usable_model_estimate_count,
        "usable_model_estimate_rate": usable_rate,
        "fill_count": fill_count,
        "orderbook_error_count": orderbook_error_count,
        "rejected_order_count": rejected_order_count,
        "simulated_unfilled_notional": unfilled_notional,
        "average_slippage": average_slippage,
    }

    blockers: list[str] = []
    if run_count < effective_config.min_run_count:
        blockers.append("insufficient shadow runs")
    if model_estimate_count < effective_config.min_model_estimate_count:
        blockers.append("insufficient model estimates")
    if usable_rate < effective_config.min_usable_estimate_rate:
        blockers.append("usable model estimate rate below minimum")
    if fill_count < effective_config.min_fill_count:
        blockers.append("insufficient fills")
    if orderbook_error_count > effective_config.max_orderbook_error_count:
        blockers.append("orderbook errors present")
    if rejected_order_count > effective_config.max_rejected_order_count:
        blockers.append("rejected orders present")
    if unfilled_notional > effective_config.max_unfilled_notional:
        blockers.append("unfilled notional present")
    if fill_count and average_slippage > effective_config.max_average_slippage:
        blockers.append("average slippage above maximum")

    warnings = [str(warning) for warning in report.get("data_quality_warnings") or []]

    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "metrics": metrics,
        "thresholds": asdict(effective_config),
    }
