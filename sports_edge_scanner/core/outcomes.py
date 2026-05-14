from dataclasses import dataclass

from sports_edge_scanner.models import Market, MarketOutcome


@dataclass(frozen=True)
class BinaryOutcomeSides:
    yes: MarketOutcome | None
    no: MarketOutcome | None

    @property
    def yes_name(self) -> str | None:
        return self.yes.name if self.yes else None

    @property
    def no_name(self) -> str | None:
        return self.no.name if self.no else None

    @property
    def yes_price(self) -> float | None:
        return self.yes.price if self.yes else None

    @property
    def no_price(self) -> float | None:
        return self.no.price if self.no else None


def _find_named_outcome(market: Market, name: str) -> MarketOutcome | None:
    wanted = name.upper()
    for outcome in market.outcomes:
        if outcome.name.upper() == wanted:
            return outcome
    return None


def binary_outcome_sides(market: Market) -> BinaryOutcomeSides:
    explicit_yes = _find_named_outcome(market, "YES")
    explicit_no = _find_named_outcome(market, "NO")
    if explicit_yes is not None and explicit_no is not None:
        return BinaryOutcomeSides(explicit_yes, explicit_no)

    if len(market.outcomes) == 2:
        if explicit_yes is not None:
            inferred_no = next(
                outcome for outcome in market.outcomes if outcome != explicit_yes
            )
            return BinaryOutcomeSides(explicit_yes, inferred_no)
        if explicit_no is not None:
            inferred_yes = next(
                outcome for outcome in market.outcomes if outcome != explicit_no
            )
            return BinaryOutcomeSides(inferred_yes, explicit_no)
        return BinaryOutcomeSides(market.outcomes[0], market.outcomes[1])

    if explicit_yes is not None or explicit_no is not None:
        return BinaryOutcomeSides(explicit_yes, explicit_no)

    return BinaryOutcomeSides(None, None)
