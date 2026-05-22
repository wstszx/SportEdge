import pytest

from sports_edge_scanner.cli import (
    _app,
    _monitor_paper,
    _shadow_diagnose,
    build_parser,
    fair_probabilities_for_market,
    market_snapshot,
    parse_fair_probability_args,
)
from sports_edge_scanner.core.events import read_events
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


def test_market_snapshot_uses_named_binary_outcomes_as_price_sides():
    market = make_market()
    named_market = Market(
        **{
            **market.__dict__,
            "outcomes": [
                MarketOutcome(name="OVER 5.5", price=0.635),
                MarketOutcome(name="UNDER 5.5", price=0.365),
            ],
        }
    )

    snapshot = market_snapshot(named_market)

    assert snapshot["yes_outcome_name"] == "OVER 5.5"
    assert snapshot["no_outcome_name"] == "UNDER 5.5"
    assert snapshot["yes_price"] == 0.635
    assert snapshot["no_price"] == 0.365
    assert snapshot["yes_break_even"] == pytest.approx(0.635)
    assert snapshot["no_break_even"] == pytest.approx(0.365)


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


def test_parser_supports_monitor_paper_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "monitor",
            "paper",
            "--limit",
            "12",
            "--interval-seconds",
            "60",
            "--snapshots",
            "snapshots.jsonl",
            "--events",
            "shadow.jsonl",
        ]
    )

    assert args.command == "monitor"
    assert args.monitor_command == "paper"
    assert args.limit == 12
    assert args.interval_seconds == 60.0
    assert args.snapshots == "snapshots.jsonl"
    assert args.events == "shadow.jsonl"


def test_parser_supports_shadow_diagnose_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "shadow",
            "diagnose",
            "--events",
            "shadow.jsonl",
            "--min-edges",
            "0.03,0.02,0.01",
            "--json",
        ]
    )

    assert args.command == "shadow"
    assert args.shadow_command == "diagnose"
    assert args.events == "shadow.jsonl"
    assert args.min_edges == "0.03,0.02,0.01"
    assert args.json is True


def test_shadow_diagnose_prints_json_report(tmp_path, capsys):
    events_path = tmp_path / "shadow_events.jsonl"
    events_path.write_text(
        "\n".join(
            [
                '{"event_type":"orderbook_snapshot","token_id":"t1",'
                '"bids":[{"price":0.50,"size":100}],'
                '"asks":[{"price":0.52,"size":100}]}',
                '{"event_type":"model_estimate","token_id":"t1","market_id":"m1",'
                '"market_slug":"market-1","outcome_name":"YES","probability":0.55,'
                '"usable":true,"reasons":["usable automatic estimate"]}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    parser = build_parser()
    args = parser.parse_args(
        [
            "shadow",
            "diagnose",
            "--events",
            str(events_path),
            "--min-edges",
            "0.03,0.02",
            "--json",
        ]
    )

    assert _shadow_diagnose(args) == 0
    output = capsys.readouterr().out
    assert '"candidate_count": 1' in output
    assert '"min_edge": 0.03' in output


def test_monitor_paper_writes_iteration_error_event(monkeypatch, tmp_path):
    class FailingMarketClient:
        def fetch_markets(self, limit):
            raise RuntimeError("temporary data failure")

    monkeypatch.setattr("sports_edge_scanner.cli.PolymarketClient", FailingMarketClient)

    parser = build_parser()
    events_path = tmp_path / "shadow_events.jsonl"
    snapshots_path = tmp_path / "market_snapshots.jsonl"
    args = parser.parse_args(
        [
            "monitor",
            "paper",
            "--iterations",
            "1",
            "--events",
            str(events_path),
            "--snapshots",
            str(snapshots_path),
        ]
    )

    assert _monitor_paper(args) == 1
    events = read_events(events_path)
    assert events[0]["event_type"] == "monitor_iteration_error"
    assert events[0]["iteration"] == 1
    assert events[0]["error"] == "temporary data failure"


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


def test_parser_supports_app_command():
    parser = build_parser()

    args = parser.parse_args(
        ["app", "--host", "127.0.0.1", "--port", "8502", "--no-browser", "--live"]
    )

    assert args.command == "app"
    assert args.host == "127.0.0.1"
    assert args.port == 8502
    assert args.no_browser is True
    assert args.live is True


def test_app_command_launches_dashboard(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "sports_edge_scanner.cli.launch_app",
        lambda config: calls.append(config) or 0,
    )

    parser = build_parser()
    args = parser.parse_args(["app", "--host", "127.0.0.1", "--port", "8502"])

    assert _app(args) == 0
    assert calls[0].host == "127.0.0.1"
    assert calls[0].port == 8502


def test_app_command_runs_shadow_watch_before_dashboard(monkeypatch):
    calls = []

    def fake_shadow_watch(args):
        calls.append(("watch", args.shadow_command))
        return 0

    def fake_launch_app(config):
        calls.append(("app", config.port))
        return 0

    monkeypatch.setattr("sports_edge_scanner.cli._shadow_watch", fake_shadow_watch)
    monkeypatch.setattr("sports_edge_scanner.cli.launch_app", fake_launch_app)

    parser = build_parser()
    args = parser.parse_args(["app", "--shadow-watch", "--watch-iterations", "1"])

    assert _app(args) == 0
    assert calls == [("watch", "watch"), ("app", 8501)]


def test_app_live_flag_prints_safety_message(monkeypatch, capsys):
    monkeypatch.setattr("sports_edge_scanner.cli.launch_app", lambda config: 0)

    parser = build_parser()
    args = parser.parse_args(["app", "--live"])

    assert _app(args) == 0
    output = capsys.readouterr().out
    assert "Live mode is controlled from the dashboard mode switch" in output
