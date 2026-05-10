import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sports_edge_scanner.core.pricing import validate_probability
from sports_edge_scanner.models import Market, MarketOutcome


@dataclass(frozen=True)
class FairProbabilityBook:
    markets: dict[str, dict[str, float]] = field(default_factory=dict)
    tokens: dict[str, float] = field(default_factory=dict)


def _validate_probability(value: Any) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("fair probability must be numeric") from exc
    return validate_probability(probability, "fair probability")


def load_fair_probability_book(path: Path) -> FairProbabilityBook:
    if not path.exists():
        raise ValueError(f"fair probability file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets: dict[str, dict[str, float]] = {}
    for market_key, outcomes in dict(payload.get("markets") or {}).items():
        markets[str(market_key)] = {
            str(outcome_name): _validate_probability(probability)
            for outcome_name, probability in dict(outcomes).items()
        }
    tokens = {
        str(token_id): _validate_probability(probability)
        for token_id, probability in dict(payload.get("tokens") or {}).items()
    }
    return FairProbabilityBook(markets=markets, tokens=tokens)


def fair_probability_for_outcome(
    market: Market,
    outcome: MarketOutcome,
    book: FairProbabilityBook,
) -> float | None:
    if outcome.token_id and outcome.token_id in book.tokens:
        return book.tokens[outcome.token_id]
    for market_key in (market.id, market.slug):
        outcome_probabilities = book.markets.get(market_key, {})
        for outcome_key, probability in outcome_probabilities.items():
            if outcome_key.upper() == outcome.name.upper():
                return probability
    return None
