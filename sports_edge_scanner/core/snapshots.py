import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from sports_edge_scanner.core.outcomes import binary_outcome_sides
from sports_edge_scanner.core.pricing import break_even_probability
from sports_edge_scanner.models import Market, Signal


def _price_for(market: Market, outcome_name: str) -> float | None:
    sides = binary_outcome_sides(market)
    if outcome_name.upper() == "YES":
        return sides.yes_price
    if outcome_name.upper() == "NO":
        return sides.no_price
    return None


def _break_even_for(market: Market, outcome_name: str) -> float | None:
    price = _price_for(market, outcome_name)
    if price is None:
        return None
    return break_even_probability(price)


def market_snapshot_record(
    market: Market,
    signal: Signal,
    timestamp: str | None = None,
) -> dict[str, Any]:
    sides = binary_outcome_sides(market)
    return {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "source": market.source,
        "market_id": market.id,
        "title": market.title,
        "slug": market.slug,
        "end_time": market.end_time,
        "active": market.active,
        "closed": market.closed,
        "liquidity": market.liquidity,
        "volume": market.volume,
        "yes_outcome_name": sides.yes_name,
        "no_outcome_name": sides.no_name,
        "yes_price": sides.yes_price,
        "no_price": sides.no_price,
        "yes_break_even": _break_even_for(market, "YES"),
        "no_break_even": _break_even_for(market, "NO"),
        "signal_status": signal.status,
        "signal_side": signal.side,
        "signal_edge": signal.edge,
        "signal_kelly_fraction": signal.kelly_fraction,
        "signal_reasons": signal.reasons,
    }


def append_snapshots(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            count += 1
    return count


def read_snapshots(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def run_snapshot_watch(
    collect_once: Callable[[], int],
    iterations: int,
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> list[int]:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")

    counts: list[int] = []
    for index in range(iterations):
        counts.append(collect_once())
        if index < iterations - 1:
            sleep(interval_seconds)
    return counts
