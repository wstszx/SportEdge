from typing import Any

from sports_edge_scanner.core.shadow_state import build_shadow_state


def _warnings(state: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if state["orderbook_error_count"]:
        warnings.append("orderbook errors present")
    if state["rejected_order_count"]:
        warnings.append("rejected orders present")
    if state["simulated_unfilled_notional"]:
        warnings.append("unfilled shadow orders present")
    if state["candidate_count"] and not state["simulated_notional_filled"]:
        warnings.append("candidates present but no fills")
    return warnings


def build_shadow_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    state = build_shadow_state(events)
    return {
        **state,
        "data_quality_warnings": _warnings(state),
    }
