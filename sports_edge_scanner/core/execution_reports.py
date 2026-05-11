from typing import Any


TERMINAL_EXECUTION_EVENTS = {
    "execution_dry_run",
    "execution_order",
    "execution_rejected",
}

SUBMITTED_STATUSES = {
    "submitted",
    "accepted",
    "open",
    "matched",
    "filled",
    "partially_filled",
    "dry_run_accepted",
}


def _number(value: Any) -> float:
    return float(value or 0.0)


def _event_time(event: dict[str, Any]) -> str:
    return str(event.get("timestamp") or "")


def _reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _empty_order(client_order_id: str) -> dict[str, Any]:
    return {
        "timestamp": "",
        "run_id": "",
        "client_order_id": client_order_id,
        "market_id": "",
        "market_slug": "",
        "outcome_name": "",
        "token_id": "",
        "side": "",
        "order_type": "",
        "limit_price": None,
        "notional": 0.0,
        "time_in_force": "",
        "guard_allowed": None,
        "guard_reasons": [],
        "status": None,
        "venue_order_id": "",
        "filled_notional": 0.0,
        "remaining_notional": 0.0,
        "average_price": None,
        "message": "",
    }


def build_execution_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    primary_terminal_keys = {
        (str(event.get("run_id") or ""), str(event.get("client_order_id") or ""))
        for event in events
        if str(event.get("event_type") or "") in TERMINAL_EXECUTION_EVENTS
    }
    run_ids: set[str] = set()
    orders: dict[str, dict[str, Any]] = {}
    intent_count = 0
    guard_allowed_count = 0
    guard_rejected_count = 0
    submitted_order_count = 0
    rejected_order_count = 0
    terminal_event_count = 0
    filled_notional = 0.0
    remaining_notional = 0.0
    latest_status = None
    latest_status_time = ""
    status_counts: dict[str, int] = {}
    guard_rejections_by_reason: dict[str, int] = {}

    for event in events:
        run_id = str(event.get("run_id") or "")
        if run_id:
            run_ids.add(run_id)
        event_type = str(event.get("event_type") or "")

        if event_type == "execution_intent":
            intent_count += 1
            client_order_id = str(event.get("client_order_id") or "")
            order = orders.setdefault(client_order_id, _empty_order(client_order_id))
            order.update(
                {
                    "timestamp": event.get("timestamp") or order["timestamp"],
                    "run_id": run_id,
                    "market_id": event.get("market_id") or "",
                    "market_slug": event.get("market_slug") or "",
                    "outcome_name": event.get("outcome_name") or "",
                    "token_id": event.get("token_id") or "",
                    "side": event.get("side") or "",
                    "order_type": event.get("order_type") or "",
                    "limit_price": event.get("limit_price"),
                    "notional": _number(event.get("notional")),
                    "time_in_force": event.get("time_in_force") or "",
                }
            )
            continue

        if event_type == "live_guard_decision":
            allowed = bool(event.get("allowed"))
            if allowed:
                guard_allowed_count += 1
            else:
                guard_rejected_count += 1
                for reason in _reasons(event.get("reasons")):
                    guard_rejections_by_reason[reason] = (
                        guard_rejections_by_reason.get(reason, 0) + 1
                    )
            run_orders = [order for order in orders.values() if order["run_id"] == run_id]
            if run_orders:
                order = run_orders[-1]
                order["guard_allowed"] = allowed
                order["guard_reasons"] = _reasons(event.get("reasons"))
            continue

        terminal_key = (run_id, str(event.get("client_order_id") or ""))
        is_primary_terminal = event_type in TERMINAL_EXECUTION_EVENTS
        is_result_fallback = (
            event_type == "execution_result" and terminal_key not in primary_terminal_keys
        )
        if is_primary_terminal or is_result_fallback:
            terminal_event_count += 1
            status = str(event.get("status") or "unknown")
            if event_type != "execution_rejected" and status in SUBMITTED_STATUSES:
                submitted_order_count += 1
            else:
                rejected_order_count += 1

            status_counts[status] = status_counts.get(status, 0) + 1
            filled_notional += _number(event.get("filled_notional"))
            remaining_notional += _number(event.get("remaining_notional"))
            event_time = _event_time(event)
            if event_time >= latest_status_time:
                latest_status_time = event_time
                latest_status = status

            client_order_id = str(event.get("client_order_id") or "")
            order = orders.setdefault(client_order_id, _empty_order(client_order_id))
            order.update(
                {
                    "timestamp": event.get("timestamp") or order["timestamp"],
                    "run_id": run_id or order["run_id"],
                    "status": status,
                    "venue_order_id": event.get("venue_order_id") or "",
                    "filled_notional": _number(event.get("filled_notional")),
                    "remaining_notional": _number(event.get("remaining_notional")),
                    "average_price": event.get("average_price"),
                    "message": event.get("message") or "",
                }
            )

    return {
        "run_count": len(run_ids),
        "run_ids": sorted(run_ids),
        "intent_count": intent_count,
        "guard_allowed_count": guard_allowed_count,
        "guard_rejected_count": guard_rejected_count,
        "submitted_order_count": submitted_order_count,
        "rejected_order_count": rejected_order_count,
        "terminal_event_count": terminal_event_count,
        "filled_notional": filled_notional,
        "remaining_notional": remaining_notional,
        "latest_status": latest_status,
        "status_counts": status_counts,
        "guard_rejections_by_reason": guard_rejections_by_reason,
        "orders": sorted(orders.values(), key=lambda row: row["timestamp"]),
    }
