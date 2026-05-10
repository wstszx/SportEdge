import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from sports_edge_scanner.connectors.polymarket import PolymarketClient
from sports_edge_scanner.connectors.polymarket_clob import PolymarketCLOBClient
from sports_edge_scanner.core.events import read_events
from sports_edge_scanner.core.fair import FairProbabilityBook, load_fair_probability_book
from sports_edge_scanner.core.ledger import (
    append_record,
    paper_settlement_record,
    paper_trade_record,
    read_records,
)
from sports_edge_scanner.core.pricing import break_even_probability
from sports_edge_scanner.core.reports import build_quality_report, build_report
from sports_edge_scanner.core.risk import RiskConfig
from sports_edge_scanner.core.shadow_config import write_shadow_config_templates
from sports_edge_scanner.core.shadow_pipeline import run_shadow_scan
from sports_edge_scanner.core.shadow_reports import build_shadow_report
from sports_edge_scanner.core.signals import classify_market
from sports_edge_scanner.core.snapshots import (
    append_snapshots,
    market_snapshot_record,
    read_snapshots,
    run_snapshot_watch,
)
from sports_edge_scanner.models import Market, Signal


@dataclass(frozen=True)
class FairProbabilitySpecs:
    global_probabilities: dict[str, float] = field(default_factory=dict)
    scoped_probabilities: dict[str, dict[str, float]] = field(default_factory=dict)


def parse_fair_probability_args(values: Sequence[str] | None) -> FairProbabilitySpecs:
    global_probabilities: dict[str, float] = {}
    scoped_probabilities: dict[str, dict[str, float]] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--fair must use SIDE=PROB or MARKET_SLUG:SIDE=PROB")
        left, raw_probability = value.split("=", 1)
        probability = float(raw_probability)
        if probability < 0.0 or probability > 1.0:
            raise ValueError("fair probability must be between 0 and 1")

        if ":" in left:
            market_slug, side = left.split(":", 1)
            side = side.upper()
            _validate_side(side)
            scoped_probabilities.setdefault(market_slug, {})[side] = probability
        else:
            side = left.upper()
            _validate_side(side)
            global_probabilities[side] = probability

    return FairProbabilitySpecs(
        global_probabilities=global_probabilities,
        scoped_probabilities=scoped_probabilities,
    )


def _validate_side(side: str) -> None:
    if side not in {"YES", "NO"}:
        raise ValueError("fair probability side must be YES or NO")


def fair_probabilities_for_market(
    market: Market,
    specs: FairProbabilitySpecs,
) -> dict[str, float]:
    probabilities = dict(specs.global_probabilities)
    probabilities.update(specs.scoped_probabilities.get(market.slug, {}))
    probabilities.update(specs.scoped_probabilities.get(market.id, {}))
    return probabilities


def _price_for(market: Market, outcome_name: str) -> float | None:
    wanted = outcome_name.upper()
    for outcome in market.outcomes:
        if outcome.name.upper() == wanted:
            return outcome.price
    return None


def _break_even_for(market: Market, outcome_name: str) -> float | None:
    price = _price_for(market, outcome_name)
    if price is None:
        return None
    return break_even_probability(price)


def market_snapshot(market: Market) -> dict[str, object]:
    return {
        "id": market.id,
        "title": market.title,
        "slug": market.slug,
        "liquidity": market.liquidity,
        "volume": market.volume,
        "yes_price": _price_for(market, "YES"),
        "no_price": _price_for(market, "NO"),
        "yes_break_even": _break_even_for(market, "YES"),
        "no_break_even": _break_even_for(market, "NO"),
        "outcomes": [
            {
                "name": outcome.name,
                "price": outcome.price,
                "token_id": outcome.token_id,
            }
            for outcome in market.outcomes
        ],
        "source": market.source,
    }


def _scan(args: argparse.Namespace) -> int:
    client = PolymarketClient()
    try:
        fair_specs = parse_fair_probability_args(args.fair)
    except ValueError as exc:
        print(f"scan failed: {exc}", file=sys.stderr)
        return 2

    try:
        markets = client.fetch_markets(limit=args.limit)
    except Exception as exc:
        print(f"scan failed: {exc}", file=sys.stderr)
        return 1

    signals = [
        classify_market(market, fair_probabilities_for_market(market, fair_specs))
        for market in markets
    ]
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "market": market_snapshot(market),
                        "signal": signal.to_dict(),
                    }
                    for market, signal in zip(markets, signals)
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if not markets:
        print("No sports-like Polymarket markets found.")
        return 0

    for market, signal in zip(markets, signals):
        _print_market_signal(market, signal)
    return 0


def _fetch_markets_and_signals(
    limit: int,
    fair_values: Sequence[str] | None,
) -> tuple[list[Market], list[Signal]]:
    fair_specs = parse_fair_probability_args(fair_values)
    markets = PolymarketClient().fetch_markets(limit=limit)
    signals = [
        classify_market(market, fair_probabilities_for_market(market, fair_specs))
        for market in markets
    ]
    return markets, signals


def _print_market_signal(market: Market, signal: Signal) -> None:
    yes_price = _price_for(market, "YES")
    no_price = _price_for(market, "NO")
    print(f"[{signal.status.upper()}] {market.title}")
    print(f"  Platform: {market.source}")
    print(f"  YES price: {_format_price(yes_price)} | NO price: {_format_price(no_price)}")
    print(
        "  Break-even: "
        f"YES {_format_percent(_break_even_for(market, 'YES'))} | "
        f"NO {_format_percent(_break_even_for(market, 'NO'))}"
    )
    print(f"  Liquidity: ${market.liquidity:,.2f} | Volume: ${market.volume:,.2f}")
    print(f"  Reasons: {', '.join(signal.reasons)}")
    if signal.side:
        print(
            "  Candidate: "
            f"{signal.side} at {_format_price(signal.price)} | "
            f"edge {signal.edge:.2%} | Kelly {signal.kelly_fraction:.2%}"
        )
    print()


def _format_price(price: float | None) -> str:
    if price is None:
        return "n/a"
    return f"{price:.3f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _paper_add(args: argparse.Namespace) -> int:
    try:
        metadata = {}
        if args.market_id:
            metadata["market_id"] = args.market_id
        record = paper_trade_record(
            market=args.market,
            side=args.side,
            price=args.price,
            size=args.size,
            note=args.note,
            metadata=metadata,
        )
        append_record(Path(args.ledger), record)
    except ValueError as exc:
        print(f"paper add failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(record, sort_keys=True))
    return 0


def _paper_settle(args: argparse.Namespace) -> int:
    try:
        record = paper_settlement_record(
            market=args.market,
            market_id=args.market_id,
            winning_side=args.winning_side,
            note=args.note,
        )
        append_record(Path(args.ledger), record)
    except ValueError as exc:
        print(f"paper settle failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(record, sort_keys=True))
    return 0


def _snapshot_collect(args: argparse.Namespace) -> int:
    try:
        count = _collect_snapshot_records(args.limit, args.fair, Path(args.snapshots))
    except ValueError as exc:
        print(f"snapshot collect failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"snapshot collect failed: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {count} snapshot records to {args.snapshots}")
    return 0


def _collect_snapshot_records(
    limit: int,
    fair_values: Sequence[str] | None,
    snapshot_path: Path,
) -> int:
    markets, signals = _fetch_markets_and_signals(limit, fair_values)
    records = [
        market_snapshot_record(market, signal)
        for market, signal in zip(markets, signals)
    ]
    return append_snapshots(snapshot_path, records)


def _snapshot_watch(args: argparse.Namespace) -> int:
    def collect_once() -> int:
        count = _collect_snapshot_records(args.limit, args.fair, Path(args.snapshots))
        print(f"wrote {count} snapshot records to {args.snapshots}")
        return count

    try:
        counts = run_snapshot_watch(
            collect_once=collect_once,
            iterations=args.iterations,
            interval_seconds=args.interval_seconds,
        )
    except ValueError as exc:
        print(f"snapshot watch failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"snapshot watch failed: {exc}", file=sys.stderr)
        return 1

    print(f"completed {len(counts)} snapshot iterations")
    return 0


def _report(args: argparse.Namespace) -> int:
    paper_records = read_records(Path(args.ledger))
    snapshots = read_snapshots(Path(args.snapshots))
    report = build_report(paper_records, snapshots)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print(f"Paper trades: {report['paper_trades']}")
    print(f"Settlements: {report['settlements']}")
    print(f"Settled trades: {report['settled_trades']}")
    print(f"Snapshots: {report['snapshots']}")
    print(f"Open trades with marks: {report['open_trades_with_marks']}")
    print(f"Total staked: ${report['total_staked']:,.2f}")
    print(f"Mark-to-market PnL: ${report['mark_to_market_pnl']:,.2f}")
    print(f"Mark-to-market ROI: {report['mark_to_market_roi']:.2%}")
    print(f"Average CLV: {report['average_clv']:.2%}")
    print(f"Realized PnL: ${report['realized_pnl']:,.2f}")
    print(f"Realized ROI: {report['realized_roi']:.2%}")
    print(f"Win rate: {report['win_rate']:.2%}")
    print(f"Max drawdown: ${report['max_drawdown']:,.2f}")
    return 0


def _quality(args: argparse.Namespace) -> int:
    paper_records = read_records(Path(args.ledger))
    snapshots = read_snapshots(Path(args.snapshots))
    report = build_quality_report(paper_records, snapshots)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print(f"Snapshots: {report['snapshot_count']}")
    print(f"Markets: {report['market_count']}")
    print(f"Snapshot time span: {report['snapshot_time_span_hours']:.2f} hours")
    print(f"Candidate snapshots: {report['candidate_snapshot_count']}")
    print(f"Snapshots missing YES/NO prices: {report['missing_price_snapshot_count']}")
    print(f"Paper trades: {report['paper_trade_count']}")
    print(f"Paper trades missing snapshots: {report['paper_trades_missing_snapshots']}")
    if report["markets"]:
        print("Top markets by snapshot count:")
        for market in report["markets"][:5]:
            print(
                "  "
                f"{market['snapshot_count']} snapshots | "
                f"{market['time_span_hours']:.2f}h | "
                f"{market['market_id']} | "
                f"{market['title']}"
            )
    return 0


def _load_risk_config(path_value: str) -> RiskConfig:
    if not path_value:
        return RiskConfig()
    payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
    return RiskConfig(**payload)


def _shadow_scan(args: argparse.Namespace) -> int:
    try:
        fair_book = (
            load_fair_probability_book(Path(args.fair))
            if args.fair
            else FairProbabilityBook()
        )
        summary = run_shadow_scan(
            market_client=PolymarketClient(),
            book_client=PolymarketCLOBClient(),
            fair_book=fair_book,
            risk_config=_load_risk_config(args.config),
            limit=args.limit,
            events_path=Path(args.events),
            run_id=str(uuid4()),
        )
    except Exception as exc:
        print(f"shadow scan failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Markets: {summary['markets']}")
        print(f"Candidates: {summary['candidate_count']}")
        print(f"Accepted shadow orders: {summary['accepted_order_count']}")
        print(f"Rejected shadow orders: {summary['rejected_order_count']}")
        print(f"Events: {summary['events_path']}")
    return 0


def _shadow_report(args: argparse.Namespace) -> int:
    report = build_shadow_report(read_events(Path(args.events)))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Candidates: {report['candidate_count']}")
        print(f"Accepted shadow orders: {report['accepted_order_count']}")
        print(f"Rejected shadow orders: {report['rejected_order_count']}")
        print(f"Simulated notional filled: ${report['simulated_notional_filled']:,.2f}")
        print(f"Average slippage: {report['average_slippage']:.4f}")
    return 0


def run_shadow_smoke(market_client, book_client, limit: int) -> dict[str, object]:
    warnings: list[str] = []
    failures: list[dict[str, str]] = []
    markets = market_client.fetch_markets(limit=limit)
    attempted = 0
    succeeded = 0

    for market in markets:
        for outcome in market.outcomes:
            if not outcome.token_id:
                continue
            attempted += 1
            try:
                book_client.fetch_orderbook(outcome.token_id)
                succeeded += 1
            except Exception as exc:
                failures.append(
                    {
                        "market_id": market.id,
                        "token_id": outcome.token_id,
                        "error": str(exc),
                    }
                )

    if not markets:
        warnings.append("no markets found")
    if markets and attempted == 0:
        warnings.append("no token ids found")
    if attempted and succeeded == 0:
        warnings.append("all orderbook fetches failed")
    elif failures:
        warnings.append("some orderbook fetches failed")

    return {
        "ok": bool(markets) and attempted > 0 and succeeded == attempted,
        "markets_found": len(markets),
        "orderbooks_attempted": attempted,
        "orderbooks_succeeded": succeeded,
        "orderbooks_failed": len(failures),
        "warnings": warnings,
        "failures": failures,
    }


def shadow_smoke_exit_code(result: dict[str, object]) -> int:
    return 0 if result.get("ok") is True else 1


def _shadow_smoke(args: argparse.Namespace) -> int:
    try:
        result = run_shadow_smoke(
            market_client=PolymarketClient(),
            book_client=PolymarketCLOBClient(),
            limit=args.limit,
        )
    except Exception as exc:
        print(f"shadow smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Markets found: {result['markets_found']}")
        print(f"Orderbooks attempted: {result['orderbooks_attempted']}")
        print(f"Orderbooks succeeded: {result['orderbooks_succeeded']}")
        print(f"Orderbooks failed: {result['orderbooks_failed']}")
        if result["warnings"]:
            print(f"Warnings: {', '.join(result['warnings'])}")
    return shadow_smoke_exit_code(result)


def _shadow_init_config(args: argparse.Namespace) -> int:
    try:
        written = write_shadow_config_templates(
            Path(args.config),
            Path(args.fair),
            force=args.force,
        )
    except FileExistsError as exc:
        print(f"shadow init-config failed: {exc}", file=sys.stderr)
        return 2

    for path in written:
        print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sports_edge_scanner",
        description="Research-only sports prediction-market signal scanner.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan public Polymarket sports-like markets.")
    scan.add_argument("--limit", type=int, default=20, help="Maximum markets to fetch.")
    scan.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    scan.add_argument(
        "--fair",
        action="append",
        default=[],
        help="Fair probability as SIDE=PROB or MARKET_SLUG:SIDE=PROB. Example: --fair YES=0.55",
    )
    scan.set_defaults(func=_scan)

    paper = subparsers.add_parser("paper", help="Manage paper-trading records.")
    paper_subparsers = paper.add_subparsers(dest="paper_command", required=True)
    add = paper_subparsers.add_parser("add", help="Append a paper-trade record.")
    add.add_argument("--ledger", default="paper_trades.jsonl", help="JSONL ledger path.")
    add.add_argument("--market", required=True, help="Market title or identifier.")
    add.add_argument("--side", required=True, choices=["YES", "NO", "yes", "no"])
    add.add_argument("--price", required=True, type=float)
    add.add_argument("--size", required=True, type=float)
    add.add_argument("--note", default="")
    add.add_argument("--market-id", default="", help="Market id for matching snapshots.")
    add.set_defaults(func=_paper_add)

    settle = paper_subparsers.add_parser("settle", help="Append a settlement record.")
    settle.add_argument("--ledger", default="paper_trades.jsonl", help="JSONL ledger path.")
    settle.add_argument("--market", required=True, help="Market title or identifier.")
    settle.add_argument("--market-id", required=True, help="Market id to settle.")
    settle.add_argument(
        "--winning-side",
        required=True,
        choices=["YES", "NO", "yes", "no"],
        help="Resolved winning side.",
    )
    settle.add_argument("--note", default="")
    settle.set_defaults(func=_paper_settle)

    snapshot = subparsers.add_parser("snapshot", help="Collect market snapshots.")
    snapshot_subparsers = snapshot.add_subparsers(dest="snapshot_command", required=True)
    collect = snapshot_subparsers.add_parser("collect", help="Append scan snapshots to JSONL.")
    collect.add_argument("--limit", type=int, default=50)
    collect.add_argument("--snapshots", default="market_snapshots.jsonl")
    collect.add_argument(
        "--fair",
        action="append",
        default=[],
        help="Fair probability as SIDE=PROB or MARKET_SLUG:SIDE=PROB.",
    )
    collect.set_defaults(func=_snapshot_collect)

    watch = snapshot_subparsers.add_parser("watch", help="Collect snapshots repeatedly.")
    watch.add_argument("--limit", type=int, default=50)
    watch.add_argument("--snapshots", default="market_snapshots.jsonl")
    watch.add_argument("--iterations", type=int, default=48)
    watch.add_argument("--interval-seconds", type=float, default=1800.0)
    watch.add_argument(
        "--fair",
        action="append",
        default=[],
        help="Fair probability as SIDE=PROB or MARKET_SLUG:SIDE=PROB.",
    )
    watch.set_defaults(func=_snapshot_watch)

    report = subparsers.add_parser("report", help="Summarize paper ledger and snapshots.")
    report.add_argument("--ledger", default="paper_trades.jsonl")
    report.add_argument("--snapshots", default="market_snapshots.jsonl")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=_report)

    quality = subparsers.add_parser("quality", help="Inspect snapshot and ledger data quality.")
    quality.add_argument("--ledger", default="paper_trades.jsonl")
    quality.add_argument("--snapshots", default="market_snapshots.jsonl")
    quality.add_argument("--json", action="store_true")
    quality.set_defaults(func=_quality)

    shadow = subparsers.add_parser("shadow", help="Run shadow trading simulations.")
    shadow_subparsers = shadow.add_subparsers(dest="shadow_command", required=True)

    shadow_scan = shadow_subparsers.add_parser(
        "scan",
        help="Scan markets and simulate risk-checked shadow orders.",
    )
    shadow_scan.add_argument("--limit", type=int, default=20)
    shadow_scan.add_argument("--fair", default="", help="Fair probability JSON file.")
    shadow_scan.add_argument("--config", default="", help="Shadow risk config JSON file.")
    shadow_scan.add_argument("--events", default="shadow_events.jsonl")
    shadow_scan.add_argument("--json", action="store_true")
    shadow_scan.set_defaults(func=_shadow_scan)

    shadow_report = shadow_subparsers.add_parser(
        "report",
        help="Summarize shadow event logs.",
    )
    shadow_report.add_argument("--events", default="shadow_events.jsonl")
    shadow_report.add_argument("--json", action="store_true")
    shadow_report.set_defaults(func=_shadow_report)

    shadow_smoke = shadow_subparsers.add_parser(
        "smoke",
        help="Check public Gamma and CLOB data availability without trading.",
    )
    shadow_smoke.add_argument("--limit", type=int, default=2)
    shadow_smoke.add_argument("--json", action="store_true")
    shadow_smoke.set_defaults(func=_shadow_smoke)

    shadow_init = shadow_subparsers.add_parser(
        "init-config",
        help="Write safe shadow config and fair-probability example files.",
    )
    shadow_init.add_argument("--config", default="shadow_config.json")
    shadow_init.add_argument("--fair", default="fair_probabilities.example.json")
    shadow_init.add_argument("--force", action="store_true")
    shadow_init.set_defaults(func=_shadow_init_config)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
