import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sports_edge_scanner.models import OrderBook, OrderBookLevel


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _levels(raw_levels: Any, reverse: bool) -> list[OrderBookLevel]:
    levels: list[OrderBookLevel] = []
    if not isinstance(raw_levels, list):
        return levels
    for raw_level in raw_levels:
        if not isinstance(raw_level, dict):
            continue
        price = _float_or_none(raw_level.get("price"))
        size = _float_or_none(raw_level.get("size"))
        if price is None or size is None or price <= 0.0 or price >= 1.0 or size <= 0.0:
            continue
        levels.append(OrderBookLevel(price=price, size=size))
    levels.sort(key=lambda level: level.price, reverse=reverse)
    return levels


def normalize_orderbook(payload: dict[str, Any], fallback_token_id: str) -> OrderBook:
    timestamp = str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat())
    token_id = str(payload.get("asset_id") or payload.get("token_id") or fallback_token_id)
    if not token_id:
        raise ValueError("orderbook response missing token id")
    return OrderBook(
        market_id=str(payload.get("market") or payload.get("market_id") or ""),
        token_id=token_id,
        bids=_levels(payload.get("bids"), reverse=True),
        asks=_levels(payload.get("asks"), reverse=False),
        timestamp=timestamp,
        tick_size=_float_or_none(payload.get("tick_size")),
    )


class PolymarketCLOBClient:
    def __init__(
        self,
        base_url: str = "https://clob.polymarket.com",
        attempts: int = 2,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.attempts = max(1, attempts)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)

    def fetch_orderbook(self, token_id: str) -> OrderBook:
        params = urllib.parse.urlencode({"token_id": token_id})
        url = f"{self.base_url}/book?{params}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "sports-edge-scanner/0.1.0"},
        )
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("CLOB orderbook response must be an object")
                return normalize_orderbook(payload, fallback_token_id=token_id)
            except Exception as exc:
                last_error = exc
                if attempt < self.attempts - 1:
                    time.sleep(self.retry_delay_seconds)
        assert last_error is not None
        raise last_error
