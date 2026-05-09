from typing import Any

from sports_edge_scanner.core.reports import build_quality_report, build_report


def _record_type(record: dict[str, Any]) -> str:
    return str(record.get("type", "trade"))


def _record_market_id(record: dict[str, Any]) -> str:
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and metadata.get("market_id"):
        return str(metadata["market_id"])
    return str(record.get("market_id") or record.get("market") or "")


def latest_market_rows(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        market_id = snapshot.get("market_id")
        if market_id:
            latest[str(market_id)] = snapshot

    rows = [
        {
            "market_id": str(snapshot.get("market_id")),
            "title": snapshot.get("title"),
            "slug": snapshot.get("slug"),
            "timestamp": snapshot.get("timestamp"),
            "yes_price": snapshot.get("yes_price"),
            "no_price": snapshot.get("no_price"),
            "liquidity": snapshot.get("liquidity"),
            "volume": snapshot.get("volume"),
            "signal_status": snapshot.get("signal_status"),
            "signal_reasons": ", ".join(snapshot.get("signal_reasons") or []),
        }
        for snapshot in latest.values()
    ]
    rows.sort(
        key=lambda row: (
            0 if row["signal_status"] == "candidate" else 1,
            str(row["title"]),
        )
    )
    return rows


def price_history_for_market(
    snapshots: list[dict[str, Any]],
    market_id: str,
) -> list[dict[str, Any]]:
    rows = [
        {
            "timestamp": snapshot.get("timestamp"),
            "yes_price": snapshot.get("yes_price"),
            "no_price": snapshot.get("no_price"),
            "liquidity": snapshot.get("liquidity"),
            "signal_status": snapshot.get("signal_status"),
        }
        for snapshot in snapshots
        if str(snapshot.get("market_id")) == market_id
    ]
    rows.sort(key=lambda row: str(row["timestamp"]))
    return rows


def paper_trade_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        if _record_type(record) != "trade":
            continue
        rows.append(
            {
                "timestamp": record.get("timestamp"),
                "market_id": _record_market_id(record),
                "market": record.get("market"),
                "side": record.get("side"),
                "price": record.get("price"),
                "size": record.get("size"),
                "note": record.get("note"),
            }
        )
    return rows


def settlement_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        if _record_type(record) != "settlement":
            continue
        rows.append(
            {
                "timestamp": record.get("timestamp"),
                "market_id": record.get("market_id"),
                "market": record.get("market"),
                "winning_side": record.get("winning_side"),
                "note": record.get("note"),
            }
        )
    return rows


def build_dashboard_state(
    records: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "report": build_report(records, snapshots),
        "quality": build_quality_report(records, snapshots),
        "latest_markets": latest_market_rows(snapshots),
        "paper_trades": paper_trade_rows(records),
        "settlements": settlement_rows(records),
    }
