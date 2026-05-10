from typing import Any


def build_shadow_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_count = sum(
        1
        for event in events
        if event.get("event_type") == "signal" and event.get("status") == "candidate"
    )
    accepted_order_count = 0
    rejected_order_count = 0
    rejections_by_reason: dict[str, int] = {}
    fill_status_counts: dict[str, int] = {}
    filled_notional = 0.0
    slippages: list[float] = []

    for event in events:
        event_type = event.get("event_type")
        if event_type == "risk_decision":
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
            fill_status_counts[status] = fill_status_counts.get(status, 0) + 1
            filled_notional += float(event.get("filled_notional") or 0.0)
            slippages.append(float(event.get("slippage") or 0.0))

    return {
        "candidate_count": candidate_count,
        "accepted_order_count": accepted_order_count,
        "rejected_order_count": rejected_order_count,
        "rejections_by_reason": rejections_by_reason,
        "fill_status_counts": fill_status_counts,
        "simulated_notional_filled": filled_notional,
        "average_slippage": sum(slippages) / len(slippages) if slippages else 0.0,
    }
