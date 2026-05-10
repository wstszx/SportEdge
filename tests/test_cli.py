import pytest

from sports_edge_scanner.cli import (
    build_parser,
    fair_probabilities_for_market,
    market_snapshot,
    parse_fair_probability_args,
)
from sports_edge_scanner.models import Market, MarketOutcome


def make_market():
    return Market(
        id="market-1",
        title="Will Team A win?",
        slug="team-a-win",
        active=True,
        closed=False,
        end_time=None,
        liquidity=1000.0,
        volume=2000.0,
        outcomes=[
            MarketOutcome(name="YES", price=0.47),
            MarketOutcome(name="NO", price=0.52),
        ],
        source="polymarket",
    )


def test_parse_fair_probability_args_accepts_global_and_scoped_values():
    fair_specs = parse_fair_probability_args(["YES=0.55", "team-a-win:NO=0.44"])

    assert fair_specs.global_probabilities == {"YES": 0.55}
    assert fair_specs.scoped_probabilities == {"team-a-win": {"NO": 0.44}}


def test_parse_fair_probability_args_rejects_bad_side():
    with pytest.raises(ValueError):
        parse_fair_probability_args(["MAYBE=0.55"])


def test_fair_probabilities_for_market_merges_global_and_scoped_values():
    fair_specs = parse_fair_probability_args(["YES=0.55", "team-a-win:NO=0.44"])

    assert fair_probabilities_for_market(make_market(), fair_specs) == {
        "YES": 0.55,
        "NO": 0.44,
    }


def test_market_snapshot_includes_break_even_probabilities():
    snapshot = market_snapshot(make_market())

    assert snapshot["yes_break_even"] == pytest.approx(0.47)
    assert snapshot["no_break_even"] == pytest.approx(0.52)


def test_market_snapshot_includes_generic_outcomes():
    snapshot = market_snapshot(make_market())

    assert snapshot["outcomes"] == [
        {"name": "YES", "price": 0.47, "token_id": None},
        {"name": "NO", "price": 0.52, "token_id": None},
    ]


def test_parser_supports_snapshot_collect_command():
    parser = build_parser()

    args = parser.parse_args(["snapshot", "collect", "--limit", "5"])

    assert args.command == "snapshot"
    assert args.snapshot_command == "collect"
    assert args.limit == 5


def test_parser_supports_snapshot_watch_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "snapshot",
            "watch",
            "--limit",
            "5",
            "--iterations",
            "3",
            "--interval-seconds",
            "1",
        ]
    )

    assert args.command == "snapshot"
    assert args.snapshot_command == "watch"
    assert args.limit == 5
    assert args.iterations == 3
    assert args.interval_seconds == 1.0


def test_parser_supports_report_command():
    parser = build_parser()

    args = parser.parse_args(["report", "--ledger", "paper.jsonl", "--snapshots", "snap.jsonl"])

    assert args.command == "report"
    assert args.ledger == "paper.jsonl"
    assert args.snapshots == "snap.jsonl"


def test_parser_supports_quality_command():
    parser = build_parser()

    args = parser.parse_args(
        ["quality", "--ledger", "paper.jsonl", "--snapshots", "snap.jsonl", "--json"]
    )

    assert args.command == "quality"
    assert args.ledger == "paper.jsonl"
    assert args.snapshots == "snap.jsonl"
    assert args.json is True


def test_parser_supports_paper_settle_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "paper",
            "settle",
            "--market",
            "Market 1",
            "--market-id",
            "m1",
            "--winning-side",
            "YES",
            "--note",
            "resolved",
        ]
    )

    assert args.command == "paper"
    assert args.paper_command == "settle"
    assert args.market == "Market 1"
    assert args.market_id == "m1"
    assert args.winning_side == "YES"
