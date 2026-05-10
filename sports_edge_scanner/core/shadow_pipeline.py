from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sports_edge_scanner.core.events import append_event, make_event
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig, evaluate_candidate_order
from sports_edge_scanner.core.shadow_execution import simulate_buy_limit_fill
from sports_edge_scanner.core.shadow_signals import candidate_orders_for_market
from sports_edge_scanner.models import OrderBook, ShadowOrder


def _order_id(run_id: str, index: int) -> str:
    return f"{run_id}-shadow-{index}"


def _parse_iso_datetime(value: str) -> datetime | None:
    text = value
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _orderbook_age_seconds(orderbook: OrderBook, now: datetime) -> float | None:
    parsed = _parse_iso_datetime(orderbook.timestamp)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds())


def run_shadow_scan(
    market_client: Any,
    book_client: Any,
    fair_book: FairProbabilityBook,
    risk_config: RiskConfig,
    limit: int,
    events_path: Path,
    run_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    markets = market_client.fetch_markets(limit=limit)
    candidate_count = 0
    accepted_count = 0
    rejected_count = 0
    order_index = 0
    market_exposure: dict[str, float] = {}
    total_exposure = 0.0
    current_time = now or datetime.now(timezone.utc)

    for market in markets:
        books: dict[str, OrderBook] = {}
        for outcome in market.outcomes:
            if outcome.token_id:
                try:
                    book = book_client.fetch_orderbook(outcome.token_id)
                    books[outcome.token_id] = book
                    append_event(
                        events_path,
                        make_event(
                            "orderbook_snapshot",
                            run_id,
                            {
                                "market_id": market.id,
                                "token_id": outcome.token_id,
                                **book.to_dict(),
                            },
                        ),
                    )
                except Exception as exc:
                    append_event(
                        events_path,
                        make_event(
                            "orderbook_error",
                            run_id,
                            {
                                "market_id": market.id,
                                "token_id": outcome.token_id,
                                "error": str(exc),
                            },
                        ),
                    )

        candidates = candidate_orders_for_market(
            market,
            fair_book,
            books,
            min_edge=risk_config.min_edge,
            default_notional=risk_config.max_order_notional,
        )
        for candidate in candidates:
            candidate_count += 1
            append_event(
                events_path,
                make_event(
                    "signal",
                    run_id,
                    {"status": "candidate", **candidate.to_dict()},
                ),
            )
            book = books[candidate.token_id]
            projected_order = ShadowOrder(
                order_id=_order_id(run_id, order_index + 1),
                market_id=candidate.market_id,
                outcome_name=candidate.outcome_name,
                token_id=candidate.token_id,
                side="BUY",
                limit_price=candidate.limit_price,
                notional=min(
                    candidate.requested_notional,
                    risk_config.max_order_notional,
                    max(
                        0.0,
                        risk_config.max_market_exposure
                        - market_exposure.get(candidate.market_id, 0.0),
                    ),
                    max(0.0, risk_config.max_total_exposure - total_exposure),
                ),
                source_signal_id=f"{run_id}-signal-{candidate_count}",
            )
            simulated_fill = simulate_buy_limit_fill(projected_order, book)
            decision = evaluate_candidate_order(
                candidate,
                book,
                risk_config,
                market_exposure=market_exposure.get(candidate.market_id, 0.0),
                total_exposure=total_exposure,
                daily_pnl=0.0,
                market_liquidity=market.liquidity,
                orderbook_age_seconds=_orderbook_age_seconds(book, current_time),
                simulated_fill=simulated_fill,
            )
            append_event(
                events_path,
                make_event(
                    "risk_decision",
                    run_id,
                    {
                        "market_id": candidate.market_id,
                        "token_id": candidate.token_id,
                        **decision.to_dict(),
                    },
                ),
            )
            if not decision.allowed:
                rejected_count += 1
                continue

            accepted_count += 1
            market_exposure[candidate.market_id] = (
                market_exposure.get(candidate.market_id, 0.0) + decision.approved_notional
            )
            total_exposure += decision.approved_notional
            order_index += 1
            order = ShadowOrder(
                order_id=_order_id(run_id, order_index),
                market_id=candidate.market_id,
                outcome_name=candidate.outcome_name,
                token_id=candidate.token_id,
                side="BUY",
                limit_price=candidate.limit_price,
                notional=decision.approved_notional,
                source_signal_id=f"{run_id}-signal-{candidate_count}",
            )
            append_event(events_path, make_event("shadow_order", run_id, order.to_dict()))
            fill = simulate_buy_limit_fill(order, book)
            append_event(
                events_path,
                make_event(
                    "shadow_fill",
                    run_id,
                    {
                        "market_id": candidate.market_id,
                        "outcome_name": candidate.outcome_name,
                        "token_id": candidate.token_id,
                        **fill.to_dict(),
                    },
                ),
            )

    return {
        "markets": len(markets),
        "candidate_count": candidate_count,
        "accepted_order_count": accepted_count,
        "rejected_order_count": rejected_count,
        "events_path": str(events_path),
    }
