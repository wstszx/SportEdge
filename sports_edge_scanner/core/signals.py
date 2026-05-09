from typing import Optional

from sports_edge_scanner.core.kelly import fractional_kelly
from sports_edge_scanner.core.pricing import break_even_probability, expected_value_per_unit
from sports_edge_scanner.models import Market, MarketOutcome, Signal


def _find_outcome(market: Market, name: str) -> Optional[MarketOutcome]:
    wanted = name.upper()
    for outcome in market.outcomes:
        if outcome.name.upper() == wanted:
            return outcome
    return None


def _spread(yes_price: float, no_price: float) -> float:
    return max(0.0, yes_price + no_price - 1.0)


def classify_market(
    market: Market,
    fair_probabilities: Optional[dict[str, float]] = None,
    min_edge: float = 0.02,
    min_liquidity: float = 1000.0,
    max_spread: float = 0.08,
) -> Signal:
    reasons: list[str] = []

    if market.closed or not market.active:
        return Signal(
            market_id=market.id,
            title=market.title,
            status="skip",
            reasons=["market is closed"],
            source=market.source,
        )

    yes = _find_outcome(market, "YES")
    no = _find_outcome(market, "NO")
    if yes is None or no is None or yes.price is None or no.price is None:
        return Signal(
            market_id=market.id,
            title=market.title,
            status="watch",
            reasons=["missing YES or NO price"],
            source=market.source,
        )

    if market.liquidity < min_liquidity:
        reasons.append("low liquidity")

    spread = _spread(yes.price, no.price)
    if spread >= max_spread:
        reasons.append("wide spread")
        return Signal(
            market_id=market.id,
            title=market.title,
            status="watch",
            reasons=reasons,
            source=market.source,
        )

    supplied = fair_probabilities or {}
    best_signal: Optional[Signal] = None
    for outcome in (yes, no):
        fair_probability = supplied.get(outcome.name.upper())
        if fair_probability is None:
            continue

        break_even = break_even_probability(outcome.price)
        edge = expected_value_per_unit(fair_probability, outcome.price)
        if edge < min_edge:
            continue

        best_signal = Signal(
            market_id=market.id,
            title=market.title,
            status="candidate",
            reasons=reasons or ["fair probability clears edge threshold"],
            side=outcome.name.upper(),
            price=outcome.price,
            fair_probability=fair_probability,
            break_even_probability=break_even,
            edge=edge,
            kelly_fraction=fractional_kelly(fair_probability, outcome.price),
            source=market.source,
        )
        break

    if best_signal is not None:
        return best_signal

    if supplied:
        reasons.append("no supplied fair probability clears edge threshold")
    else:
        reasons.append("no fair probability supplied")

    return Signal(
        market_id=market.id,
        title=market.title,
        status="watch",
        reasons=reasons,
        source=market.source,
    )
