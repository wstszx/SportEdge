import json

import pytest

from sports_edge_scanner.core.fair import (
    FairProbabilityBook,
    fair_probability_for_outcome,
    load_fair_probability_book,
)
from sports_edge_scanner.models import Market, MarketOutcome


def make_market():
    return Market(
        id="market-1",
        title="Team A vs Team B",
        slug="team-a-team-b",
        active=True,
        closed=False,
        end_time=None,
        liquidity=5000.0,
        volume=10000.0,
        outcomes=[
            MarketOutcome(name="Team A", price=0.46, token_id="token-a"),
            MarketOutcome(name="Team B", price=0.54, token_id="token-b"),
        ],
        source="polymarket",
    )


def test_token_probability_overrides_market_outcome_probability():
    book = FairProbabilityBook(
        markets={"market-1": {"Team A": 0.55}},
        tokens={"token-a": 0.57},
    )

    assert fair_probability_for_outcome(make_market(), make_market().outcomes[0], book) == 0.57


def test_market_id_and_slug_lookup_are_supported():
    market = make_market()
    id_book = FairProbabilityBook(markets={"market-1": {"Team A": 0.55}}, tokens={})
    slug_book = FairProbabilityBook(markets={"team-a-team-b": {"Team B": 0.48}}, tokens={})

    assert fair_probability_for_outcome(market, market.outcomes[0], id_book) == 0.55
    assert fair_probability_for_outcome(market, market.outcomes[1], slug_book) == 0.48


def test_load_fair_probability_book_validates_probabilities(tmp_path):
    path = tmp_path / "fair.json"
    path.write_text(json.dumps({"tokens": {"token-a": 1.2}}), encoding="utf-8")

    with pytest.raises(ValueError, match="fair probability"):
        load_fair_probability_book(path)
