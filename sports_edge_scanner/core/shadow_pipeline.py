from datetime import datetime
from pathlib import Path
from typing import Any

from sports_edge_scanner.core.auto_fair import AutoFairConfig
from sports_edge_scanner.core.events import append_event, make_event
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig
from sports_edge_scanner.core.shadow_execution import simulate_buy_limit_fill
from sports_edge_scanner.core.trade_pipeline import run_trade_scan
from sports_edge_scanner.models import ShadowOrder


def _order_id(run_id: str, index: int) -> str:
    return f"{run_id}-shadow-{index}"


def run_shadow_scan(
    market_client: Any,
    book_client: Any,
    fair_book: FairProbabilityBook | None,
    risk_config: RiskConfig,
    limit: int,
    events_path: Path,
    run_id: str,
    now: datetime | None = None,
    auto_fair_config: AutoFairConfig | None = None,
) -> dict[str, object]:
    def on_accepted_order(candidate, decision, book, order_index, current_time):
        order = ShadowOrder(
            order_id=_order_id(run_id, order_index),
            market_id=candidate.market_id,
            outcome_name=candidate.outcome_name,
            token_id=candidate.token_id,
            side="BUY",
            limit_price=candidate.limit_price,
            notional=decision.approved_notional,
            source_signal_id=f"{run_id}-signal-{order_index}",
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
        return {"accepted": True}

    return run_trade_scan(
        market_client=market_client,
        book_client=book_client,
        fair_book=fair_book,
        risk_config=risk_config,
        limit=limit,
        events_path=events_path,
        run_id=run_id,
        order_id_suffix="shadow",
        on_accepted_order=on_accepted_order,
        now=now,
        auto_fair_config=auto_fair_config,
    )
