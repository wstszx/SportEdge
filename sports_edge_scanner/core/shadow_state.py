from typing import Any


def build_shadow_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_count = 0
    accepted_order_count = 0
    rejected_order_count = 0
    orderbook_error_count = 0
    model_estimate_count = 0
    usable_model_estimate_count = 0
    rejections_by_reason: dict[str, int] = {}
    model_rejections_by_reason: dict[str, int] = {}
    fill_status_counts: dict[str, int] = {}
    exposure_by_market: dict[str, float] = {}
    exposure_by_outcome: dict[str, float] = {}
    fills: list[dict[str, Any]] = []
    filled_notional = 0.0
    unfilled_notional = 0.0
    slippages: list[float] = []
    risk_decisions: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type")
        if event_type == "signal" and event.get("status") == "candidate":
            candidate_count += 1
        elif event_type == "orderbook_error":
            orderbook_error_count += 1
        elif event_type == "model_estimate":
            model_estimate_count += 1
            if event.get("usable"):
                usable_model_estimate_count += 1
            else:
                for reason in event.get("reasons") or []:
                    reason_text = str(reason)
                    model_rejections_by_reason[reason_text] = (
                        model_rejections_by_reason.get(reason_text, 0) + 1
                    )
        elif event_type == "risk_decision":
            risk_decisions.append(event)
            if event.get("allowed"):
                accepted_order_count += 1
            else:
                rejected_order_count += 1
                for reason in event.get("reasons") or []:
                    reason_text = str(reason)
                    rejections_by_reason[reason_text] = (
                        rejections_by_reason.get(reason_text, 0) + 1
                    )
        elif event_type == "shadow_fill":
            status = str(event.get("status") or "unknown")
            market_id = str(event.get("market_id") or "")
            outcome_name = str(event.get("outcome_name") or event.get("token_id") or "")
            fill_notional = float(event.get("filled_notional") or 0.0)
            unfilled = float(event.get("unfilled_notional") or 0.0)
            fill_status_counts[status] = fill_status_counts.get(status, 0) + 1
            filled_notional += fill_notional
            unfilled_notional += unfilled
            slippages.append(float(event.get("slippage") or 0.0))
            if market_id and fill_notional:
                exposure_by_market[market_id] = (
                    exposure_by_market.get(market_id, 0.0) + fill_notional
                )
                exposure_key = f"{market_id}:{outcome_name}"
                exposure_by_outcome[exposure_key] = (
                    exposure_by_outcome.get(exposure_key, 0.0) + fill_notional
                )
            fills.append(event)

    return {
        "candidate_count": candidate_count,
        "accepted_order_count": accepted_order_count,
        "rejected_order_count": rejected_order_count,
        "orderbook_error_count": orderbook_error_count,
        "model_estimate_count": model_estimate_count,
        "usable_model_estimate_count": usable_model_estimate_count,
        "unusable_model_estimate_count": (
            model_estimate_count - usable_model_estimate_count
        ),
        "model_rejections_by_reason": model_rejections_by_reason,
        "simulated_notional_filled": filled_notional,
        "simulated_unfilled_notional": unfilled_notional,
        "average_slippage": sum(slippages) / len(slippages) if slippages else 0.0,
        "fill_status_counts": fill_status_counts,
        "rejections_by_reason": rejections_by_reason,
        "exposure_by_market": exposure_by_market,
        "exposure_by_outcome": exposure_by_outcome,
        "risk_decisions": risk_decisions,
        "fills": fills,
    }
