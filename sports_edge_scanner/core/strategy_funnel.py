from typing import Any


DEFAULT_MIN_EDGES = [0.03, 0.02, 0.01]


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _best_bid(event: dict[str, Any]) -> float | None:
    bids = event.get("bids") or []
    prices = [_number(level.get("price")) for level in bids if isinstance(level, dict)]
    valid_prices = [price for price in prices if price is not None]
    return max(valid_prices) if valid_prices else None


def _best_ask(event: dict[str, Any]) -> float | None:
    asks = event.get("asks") or []
    prices = [_number(level.get("price")) for level in asks if isinstance(level, dict)]
    valid_prices = [price for price in prices if price is not None]
    return min(valid_prices) if valid_prices else None


def _edge_summary(edges: list[float]) -> dict[str, float]:
    if not edges:
        return {
            "min": 0.0,
            "max": 0.0,
            "average": 0.0,
        }
    return {
        "min": min(edges),
        "max": max(edges),
        "average": sum(edges) / len(edges),
    }


def _sorted_reason_counts(reason_counts: dict[str, int]) -> dict[str, int]:
    return dict(sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])))


def _event_key(event: dict[str, Any]) -> tuple[str, str]:
    return (
        str(event.get("run_id") or ""),
        str(event.get("token_id") or ""),
    )


def _primary_blockers(
    *,
    usable_estimate_count: int,
    estimates_with_orderbook_count: int,
    max_candidate_count: int,
    unusable_estimate_count: int,
) -> list[str]:
    blockers: list[str] = []
    if not usable_estimate_count:
        blockers.append("no usable model estimates")
    elif not estimates_with_orderbook_count:
        blockers.append("usable estimates are missing orderbook snapshots")
    elif max_candidate_count == 0:
        blockers.append("usable estimates do not clear executable ask prices")
    if unusable_estimate_count:
        blockers.append("some estimates are rejected before candidate generation")
    return blockers


def _deduplicate_top_gaps(estimates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_token: dict[str, dict[str, Any]] = {}
    for estimate in estimates:
        token_id = str(estimate.get("token_id") or "")
        current = by_token.get(token_id)
        if current is None or estimate["edge_to_ask"] > current["edge_to_ask"]:
            by_token[token_id] = estimate
    return sorted(
        by_token.values(),
        key=lambda item: item["edge_to_ask"],
        reverse=True,
    )[:10]


def build_strategy_funnel_diagnostics(
    events: list[dict[str, Any]],
    min_edges: list[float] | None = None,
) -> dict[str, Any]:
    effective_min_edges = min_edges or DEFAULT_MIN_EDGES
    orderbooks_by_key: dict[tuple[str, str], dict[str, float]] = {}
    reason_counts: dict[str, int] = {}
    model_estimate_count = 0
    usable_model_estimate_count = 0
    estimates_with_orderbook: list[dict[str, Any]] = []
    edges: list[float] = []

    for event in events:
        if event.get("event_type") == "orderbook_snapshot":
            run_id, token_id = _event_key(event)
            bid = _best_bid(event)
            ask = _best_ask(event)
            if token_id and bid is not None and ask is not None:
                orderbooks_by_key[(run_id, token_id)] = {
                    "best_bid": bid,
                    "best_ask": ask,
                    "spread": max(0.0, ask - bid),
                }

    for event in events:
        if event.get("event_type") != "model_estimate":
            continue
        model_estimate_count += 1
        if not event.get("usable"):
            for reason in event.get("reasons") or []:
                reason_text = str(reason)
                reason_counts[reason_text] = reason_counts.get(reason_text, 0) + 1
            continue

        usable_model_estimate_count += 1
        run_id, token_id = _event_key(event)
        probability = _number(event.get("probability"))
        orderbook = orderbooks_by_key.get((run_id, token_id))
        if orderbook is None and not run_id:
            orderbook = orderbooks_by_key.get(("", token_id))
        if probability is None or orderbook is None:
            continue
        edge = probability - orderbook["best_ask"]
        edges.append(edge)
        estimates_with_orderbook.append(
            {
                "token_id": token_id,
                "market_id": event.get("market_id"),
                "market_slug": event.get("market_slug"),
                "outcome_name": event.get("outcome_name"),
                "probability": probability,
                "best_bid": orderbook["best_bid"],
                "best_ask": orderbook["best_ask"],
                "spread": orderbook["spread"],
                "edge_to_ask": edge,
                "source": event.get("source"),
                "confidence": event.get("confidence"),
            }
        )

    sensitivity = [
        {
            "min_edge": min_edge,
            "candidate_count": sum(1 for edge in edges if edge >= min_edge),
        }
        for min_edge in effective_min_edges
    ]
    max_candidate_count = max(
        (item["candidate_count"] for item in sensitivity),
        default=0,
    )
    top_candidate_gaps = _deduplicate_top_gaps(estimates_with_orderbook)

    unusable_estimate_count = model_estimate_count - usable_model_estimate_count
    return {
        "model_estimate_count": model_estimate_count,
        "usable_model_estimate_count": usable_model_estimate_count,
        "unusable_model_estimate_count": unusable_estimate_count,
        "estimates_with_orderbook_count": len(estimates_with_orderbook),
        "min_edge_sensitivity": sensitivity,
        "edge_summary": _edge_summary(edges),
        "model_rejections_by_reason": _sorted_reason_counts(reason_counts),
        "top_candidate_gaps": top_candidate_gaps,
        "primary_blockers": _primary_blockers(
            usable_estimate_count=usable_model_estimate_count,
            estimates_with_orderbook_count=len(estimates_with_orderbook),
            max_candidate_count=max_candidate_count,
            unusable_estimate_count=unusable_estimate_count,
        ),
    }
