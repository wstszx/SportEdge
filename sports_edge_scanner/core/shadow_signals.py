from sports_edge_scanner.core.fair import FairProbabilityBook, fair_probability_for_outcome
from sports_edge_scanner.core.pricing import expected_value_per_unit
from sports_edge_scanner.models import CandidateOrder, Market, OrderBook


def candidate_orders_for_market(
    market: Market,
    fair_probabilities: FairProbabilityBook,
    orderbooks_by_token: dict[str, OrderBook],
    min_edge: float = 0.03,
    cost_buffer: float = 0.0,
    default_notional: float = 10.0,
) -> list[CandidateOrder]:
    if market.closed or not market.active:
        return []

    candidates: list[CandidateOrder] = []
    for outcome in market.outcomes:
        if not outcome.token_id:
            continue
        book = orderbooks_by_token.get(outcome.token_id)
        if book is None or book.best_ask is None:
            continue
        fair = fair_probability_for_outcome(market, outcome, fair_probabilities)
        if fair is None:
            continue
        edge = expected_value_per_unit(fair, book.best_ask, cost_buffer=cost_buffer)
        if edge < min_edge:
            continue
        limit_price = min(0.999, fair - min_edge - cost_buffer)
        candidates.append(
            CandidateOrder(
                market_id=market.id,
                market_slug=market.slug,
                outcome_name=outcome.name,
                token_id=outcome.token_id,
                side="BUY",
                limit_price=limit_price,
                requested_notional=default_notional,
                fair_probability=fair,
                edge=edge,
                reason="fair probability clears executable price",
            )
        )
    return candidates
