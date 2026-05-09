from datetime import datetime
from typing import Any


def latest_snapshot_by_market(
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        market_id = snapshot.get("market_id")
        if market_id:
            latest[str(market_id)] = snapshot
    return latest


def _record_market_id(record: dict[str, Any]) -> str:
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and metadata.get("market_id"):
        return str(metadata["market_id"])
    return str(record.get("market", ""))


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _time_span_hours(timestamps: list[datetime]) -> float:
    if len(timestamps) < 2:
        return 0.0
    return (max(timestamps) - min(timestamps)).total_seconds() / 3600.0


def _mark_price(snapshot: dict[str, Any], side: str) -> float | None:
    key = "yes_price" if side.upper() == "YES" else "no_price"
    value = snapshot.get(key)
    if value is None:
        return None
    return float(value)


def _is_trade_record(record: dict[str, Any]) -> bool:
    return record.get("type", "trade") == "trade"


def _is_settlement_record(record: dict[str, Any]) -> bool:
    return record.get("type") == "settlement"


def _settlement_market_id(record: dict[str, Any]) -> str:
    return str(record.get("market_id") or record.get("market") or "")


def _realized_pnl(record: dict[str, Any], settlement: dict[str, Any]) -> float:
    entry_price = float(record["price"])
    size = float(record["size"])
    side = str(record["side"]).upper()
    winning_side = str(settlement["winning_side"]).upper()
    if side == winning_side:
        contracts = size / entry_price
        return (1.0 - entry_price) * contracts
    return -size


def _max_drawdown(cumulative_values: list[float]) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for value in cumulative_values:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, peak - value)
    return max_drawdown


def build_report(
    paper_records: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    trade_records = [record for record in paper_records if _is_trade_record(record)]
    settlement_records = [
        record for record in paper_records if _is_settlement_record(record)
    ]
    settlements_by_market = {
        _settlement_market_id(record): record for record in settlement_records
    }
    latest = latest_snapshot_by_market(snapshots)
    trade_rows: list[dict[str, Any]] = []
    total_staked = 0.0
    total_pnl = 0.0
    clv_values: list[float] = []
    realized_pnl = 0.0
    realized_wins = 0
    realized_losses = 0
    cumulative_realized: list[float] = []

    for record in trade_records:
        entry_price = float(record["price"])
        size = float(record["size"])
        side = str(record["side"]).upper()
        market_id = _record_market_id(record)
        snapshot = latest.get(market_id)
        mark_price = _mark_price(snapshot, side) if snapshot else None
        settlement = settlements_by_market.get(market_id)

        total_staked += size
        pnl = None
        clv = None
        if mark_price is not None:
            contracts = size / entry_price
            pnl = (mark_price - entry_price) * contracts
            clv = mark_price - entry_price
            total_pnl += pnl
            clv_values.append(clv)

        settled = settlement is not None
        trade_realized_pnl = None
        if settlement is not None:
            trade_realized_pnl = _realized_pnl(record, settlement)
            realized_pnl += trade_realized_pnl
            cumulative_realized.append(realized_pnl)
            if trade_realized_pnl > 0:
                realized_wins += 1
            else:
                realized_losses += 1

        trade_rows.append(
            {
                "market_id": market_id,
                "market": record.get("market"),
                "side": side,
                "entry_price": entry_price,
                "mark_price": mark_price,
                "size": size,
                "pnl": pnl,
                "clv": clv,
                "settled": settled,
                "winning_side": settlement.get("winning_side") if settlement else None,
                "realized_pnl": trade_realized_pnl,
            }
        )

    open_with_marks = sum(1 for trade in trade_rows if trade["mark_price"] is not None)
    settled_trades = realized_wins + realized_losses
    return {
        "paper_trades": len(trade_records),
        "settlements": len(settlement_records),
        "settled_trades": settled_trades,
        "open_trades_with_marks": open_with_marks,
        "snapshots": len(snapshots),
        "total_staked": total_staked,
        "mark_to_market_pnl": total_pnl,
        "mark_to_market_roi": total_pnl / total_staked if total_staked else 0.0,
        "average_clv": sum(clv_values) / len(clv_values) if clv_values else 0.0,
        "realized_pnl": realized_pnl,
        "realized_roi": realized_pnl / total_staked if total_staked else 0.0,
        "realized_wins": realized_wins,
        "realized_losses": realized_losses,
        "win_rate": realized_wins / settled_trades if settled_trades else 0.0,
        "max_drawdown": _max_drawdown(cumulative_realized),
        "trades": trade_rows,
    }


def build_quality_report(
    paper_records: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    trade_records = [record for record in paper_records if _is_trade_record(record)]
    snapshots_by_market: dict[str, list[dict[str, Any]]] = {}
    all_timestamps: list[datetime] = []
    candidate_count = 0
    missing_price_count = 0

    for snapshot in snapshots:
        market_id = snapshot.get("market_id")
        if not market_id:
            continue
        market_key = str(market_id)
        snapshots_by_market.setdefault(market_key, []).append(snapshot)

        timestamp = _parse_timestamp(snapshot.get("timestamp"))
        if timestamp is not None:
            all_timestamps.append(timestamp)

        if snapshot.get("signal_status") == "candidate":
            candidate_count += 1
        if snapshot.get("yes_price") is None or snapshot.get("no_price") is None:
            missing_price_count += 1

    markets = []
    for market_id, market_snapshots in snapshots_by_market.items():
        timestamps = [
            timestamp
            for timestamp in (
                _parse_timestamp(snapshot.get("timestamp"))
                for snapshot in market_snapshots
            )
            if timestamp is not None
        ]
        first_snapshot = market_snapshots[0]
        markets.append(
            {
                "market_id": market_id,
                "title": first_snapshot.get("title"),
                "snapshot_count": len(market_snapshots),
                "time_span_hours": _time_span_hours(timestamps),
                "candidate_snapshot_count": sum(
                    1
                    for snapshot in market_snapshots
                    if snapshot.get("signal_status") == "candidate"
                ),
                "missing_price_snapshot_count": sum(
                    1
                    for snapshot in market_snapshots
                    if snapshot.get("yes_price") is None
                    or snapshot.get("no_price") is None
                ),
            }
        )

    markets.sort(key=lambda row: (-int(row["snapshot_count"]), str(row["market_id"])))
    snapshot_market_ids = set(snapshots_by_market)
    missing_trades = [
        record
        for record in trade_records
        if _record_market_id(record) not in snapshot_market_ids
    ]

    return {
        "snapshot_count": len(snapshots),
        "market_count": len(snapshots_by_market),
        "snapshot_time_span_hours": _time_span_hours(all_timestamps),
        "candidate_snapshot_count": candidate_count,
        "missing_price_snapshot_count": missing_price_count,
        "paper_trade_count": len(trade_records),
        "paper_trades_missing_snapshots": len(missing_trades),
        "markets": markets,
    }
