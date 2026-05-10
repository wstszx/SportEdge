from dataclasses import asdict, dataclass
from typing import Any

from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.pricing import validate_probability
from sports_edge_scanner.models import Market, OrderBook


@dataclass(frozen=True)
class AutoFairConfig:
    min_confidence: float = 0.75
    min_liquidity: float = 1000.0
    max_spread: float = 0.08
    min_top_book_size: float = 10.0
    orderbook_weight: float = 1.0
    display_price_weight: float = 0.5


@dataclass(frozen=True)
class FairProbabilityEstimate:
    market_id: str
    market_slug: str
    outcome_name: str
    token_id: str
    probability: float | None
    confidence: float
    source: str
    reasons: list[str]
    usable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _top_size_at_best_prices(orderbook: OrderBook) -> float:
    best_bid = orderbook.best_bid
    best_ask = orderbook.best_ask
    if best_bid is None or best_ask is None:
        return 0.0
    bid_size = sum(level.size for level in orderbook.bids if level.price == best_bid)
    ask_size = sum(level.size for level in orderbook.asks if level.price == best_ask)
    return min(bid_size, ask_size)


def _clamp_confidence(confidence: float) -> float:
    return max(0.0, min(1.0, confidence))


def _validated_probability(value: float | None) -> float | None:
    if value is None:
        return None
    return validate_probability(value, "auto fair probability")


def estimate_fair_probabilities_for_market(
    market: Market,
    orderbooks_by_token: dict[str, OrderBook],
    config: AutoFairConfig,
) -> list[FairProbabilityEstimate]:
    estimates: list[FairProbabilityEstimate] = []
    for outcome in market.outcomes:
        if outcome.token_id is None:
            continue

        confidence = config.orderbook_weight
        probability: float | None = None
        reasons: list[str] = []
        source = "orderbook_midpoint"
        orderbook = orderbooks_by_token.get(outcome.token_id)

        if market.closed or not market.active:
            confidence = 0.0
            reasons.append("market closed or inactive")

        if orderbook is not None and orderbook.best_bid is not None and orderbook.best_ask is not None:
            probability = (orderbook.best_bid + orderbook.best_ask) / 2
            if orderbook.spread is not None and orderbook.spread > config.max_spread:
                confidence -= 0.35
                reasons.append("wide spread")
            if _top_size_at_best_prices(orderbook) < config.min_top_book_size:
                confidence -= 0.25
                reasons.append("thin top of book")
        elif outcome.price is not None:
            probability = outcome.price
            source = "display_price"
            confidence = min(confidence, config.display_price_weight, 0.55)
            reasons.append("display price only")
        else:
            source = "missing"
            confidence = 0.0
            reasons.append("missing price")

        if market.liquidity < config.min_liquidity:
            confidence -= 0.25
            reasons.append("low liquidity")

        probability = _validated_probability(probability)
        confidence = _clamp_confidence(confidence)
        usable = probability is not None and confidence >= config.min_confidence
        if usable and not reasons:
            reasons.append("usable automatic estimate")

        estimates.append(
            FairProbabilityEstimate(
                market_id=market.id,
                market_slug=market.slug,
                outcome_name=outcome.name,
                token_id=outcome.token_id,
                probability=probability,
                confidence=confidence,
                source=source,
                reasons=reasons,
                usable=usable,
            )
        )
    return estimates


def build_auto_fair_probability_book(
    markets: list[Market],
    orderbooks_by_market: dict[str, dict[str, OrderBook]],
    config: AutoFairConfig,
) -> tuple[FairProbabilityBook, list[FairProbabilityEstimate]]:
    market_probabilities: dict[str, dict[str, float]] = {}
    token_probabilities: dict[str, float] = {}
    estimates: list[FairProbabilityEstimate] = []

    for market in markets:
        market_estimates = estimate_fair_probabilities_for_market(
            market,
            orderbooks_by_market.get(market.id, {}),
            config,
        )
        estimates.extend(market_estimates)
        for estimate in market_estimates:
            if estimate.usable and estimate.probability is not None:
                token_probabilities[estimate.token_id] = estimate.probability
                market_probabilities.setdefault(market.id, {})[
                    estimate.outcome_name
                ] = estimate.probability

    return (
        FairProbabilityBook(markets=market_probabilities, tokens=token_probabilities),
        estimates,
    )
