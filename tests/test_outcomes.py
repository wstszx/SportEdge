from sports_edge_scanner.core.outcomes import binary_outcome_sides
from sports_edge_scanner.models import Market, MarketOutcome


def make_market(outcomes):
    return Market(
        id="m1",
        title="Market",
        slug="market",
        active=True,
        closed=False,
        end_time=None,
        liquidity=1000.0,
        volume=2000.0,
        outcomes=outcomes,
        source="polymarket",
    )


def test_binary_outcome_sides_prefers_explicit_yes_and_no_names():
    sides = binary_outcome_sides(
        make_market(
            [
                MarketOutcome(name="Team A", price=0.46),
                MarketOutcome(name="YES", price=0.47),
                MarketOutcome(name="NO", price=0.53),
            ]
        )
    )

    assert sides.yes_name == "YES"
    assert sides.no_name == "NO"
    assert sides.yes_price == 0.47
    assert sides.no_price == 0.53


def test_binary_outcome_sides_uses_two_named_outcomes_when_yes_no_are_absent():
    sides = binary_outcome_sides(
        make_market(
            [
                MarketOutcome(name="OVER 5.5", price=0.635),
                MarketOutcome(name="UNDER 5.5", price=0.365),
            ]
        )
    )

    assert sides.yes_name == "OVER 5.5"
    assert sides.no_name == "UNDER 5.5"
    assert sides.yes_price == 0.635
    assert sides.no_price == 0.365


def test_binary_outcome_sides_infers_missing_complement_for_two_outcomes():
    sides = binary_outcome_sides(
        make_market(
            [
                MarketOutcome(name="YES", price=0.42),
                MarketOutcome(name="Team B", price=0.58),
            ]
        )
    )

    assert sides.yes_name == "YES"
    assert sides.no_name == "Team B"
    assert sides.yes_price == 0.42
    assert sides.no_price == 0.58


def test_binary_outcome_sides_does_not_guess_for_multi_outcome_markets():
    sides = binary_outcome_sides(
        make_market(
            [
                MarketOutcome(name="Team A", price=0.2),
                MarketOutcome(name="Team B", price=0.3),
                MarketOutcome(name="Draw", price=0.5),
            ]
        )
    )

    assert sides.yes is None
    assert sides.no is None
