from dataclasses import dataclass

from sports_edge_scanner.models import CandidateOrder, OrderBook, RiskDecision, ShadowFill


@dataclass(frozen=True)
class RiskConfig:
    max_order_notional: float = 10.0
    max_market_exposure: float = 25.0
    max_total_exposure: float = 100.0
    min_liquidity: float = 1000.0
    max_spread: float = 0.08
    max_slippage: float = 0.02
    min_edge: float = 0.03
    daily_loss_limit: float = 25.0
    stale_book_seconds: int = 30


def evaluate_candidate_order(
    candidate: CandidateOrder,
    orderbook: OrderBook,
    config: RiskConfig,
    market_exposure: float,
    total_exposure: float,
    daily_pnl: float,
    market_liquidity: float | None = None,
    orderbook_age_seconds: float | None = None,
    simulated_fill: ShadowFill | None = None,
) -> RiskDecision:
    reasons: list[str] = []
    approved = candidate.requested_notional

    if daily_pnl <= -abs(config.daily_loss_limit):
        reasons.append("daily loss limit reached")
    if candidate.edge < config.min_edge:
        reasons.append("edge below minimum")
    if market_liquidity is not None and market_liquidity < config.min_liquidity:
        reasons.append("low liquidity")
    if (
        orderbook_age_seconds is not None
        and orderbook_age_seconds > config.stale_book_seconds
    ):
        reasons.append("stale orderbook")
    if simulated_fill is not None and simulated_fill.slippage > config.max_slippage:
        reasons.append("slippage above maximum")
    if orderbook.spread is None:
        reasons.append("missing spread")
    elif orderbook.spread > config.max_spread:
        reasons.append("wide spread")

    if approved > config.max_order_notional:
        approved = config.max_order_notional
        reasons.append("reduced for max_order_notional")

    remaining_market = config.max_market_exposure - market_exposure
    if remaining_market < approved:
        approved = max(0.0, remaining_market)
        reasons.append("reduced for max_market_exposure")

    remaining_total = config.max_total_exposure - total_exposure
    if remaining_total < approved:
        approved = max(0.0, remaining_total)
        reasons.append("reduced for max_total_exposure")

    if approved <= 0.0:
        reasons.append("no remaining exposure capacity")

    hard_rejections = {
        "daily loss limit reached",
        "edge below minimum",
        "missing spread",
        "low liquidity",
        "stale orderbook",
        "slippage above maximum",
        "wide spread",
        "no remaining exposure capacity",
    }
    allowed = approved > 0.0 and not any(reason in hard_rejections for reason in reasons)
    if allowed and not reasons:
        reasons.append("allowed")

    return RiskDecision(
        allowed=allowed,
        reasons=reasons,
        requested_notional=candidate.requested_notional,
        approved_notional=approved if allowed else 0.0,
    )
