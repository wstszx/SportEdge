import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sports_edge_scanner.core.pricing import validate_price


def paper_trade_record(
    market: str,
    side: str,
    price: float,
    size: float,
    note: str = "",
    timestamp: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if not market.strip():
        raise ValueError("market is required")
    normalized_side = side.upper()
    if normalized_side not in {"YES", "NO"}:
        raise ValueError("side must be YES or NO")
    if size <= 0:
        raise ValueError("size must be positive")

    return {
        "type": "trade",
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "market": market,
        "side": normalized_side,
        "price": validate_price(price),
        "size": float(size),
        "note": note,
        "metadata": metadata or {},
    }


def paper_settlement_record(
    market: str,
    market_id: str,
    winning_side: str,
    note: str = "",
    timestamp: Optional[str] = None,
) -> dict[str, Any]:
    if not market.strip():
        raise ValueError("market is required")
    if not market_id.strip():
        raise ValueError("market_id is required")
    normalized_side = winning_side.upper()
    if normalized_side not in {"YES", "NO"}:
        raise ValueError("winning_side must be YES or NO")

    return {
        "type": "settlement",
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "market": market,
        "market_id": market_id,
        "winning_side": normalized_side,
        "note": note,
    }


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records
