import json
import time
import urllib.parse
import urllib.request
from typing import Any

from sports_edge_scanner.models import Market, MarketOutcome


SPORT_KEYWORDS = {
    "arsenal",
    "baseball",
    "basketball",
    "celtics",
    "champions league",
    "dodgers",
    "epl",
    "football",
    "fifa",
    "lakers",
    "mlb",
    "nba",
    "ncaab",
    "ncaaf",
    "nfl",
    "nhl",
    "olympics",
    "premier league",
    "soccer",
    "super bowl",
    "tennis",
    "ufc",
    "world cup",
}


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _float_or_zero(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price <= 0.0 or price >= 1.0:
        return None
    return price


def _tag_labels(raw_market: dict[str, Any]) -> list[str]:
    tags = _parse_jsonish(raw_market.get("tags") or [])
    labels: list[str] = []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict):
                label = tag.get("label") or tag.get("name") or tag.get("slug")
                if label:
                    labels.append(str(label))
            elif tag:
                labels.append(str(tag))
    return labels


def is_sports_market(raw_market: dict[str, Any]) -> bool:
    category = str(raw_market.get("category") or "").lower()
    if "sport" in category:
        return True

    searchable_parts = [
        str(raw_market.get("question") or raw_market.get("title") or ""),
        str(raw_market.get("slug") or ""),
        " ".join(_tag_labels(raw_market)),
    ]
    searchable = " ".join(searchable_parts).lower()
    return any(keyword in searchable for keyword in SPORT_KEYWORDS)


def normalize_market(raw_market: dict[str, Any]) -> Market:
    outcomes = _parse_jsonish(raw_market.get("outcomes") or [])
    prices = _parse_jsonish(raw_market.get("outcomePrices") or [])
    token_ids = _parse_jsonish(raw_market.get("clobTokenIds") or [])

    normalized_outcomes: list[MarketOutcome] = []
    if isinstance(outcomes, list):
        for index, outcome in enumerate(outcomes):
            price = prices[index] if isinstance(prices, list) and index < len(prices) else None
            token_id = (
                token_ids[index]
                if isinstance(token_ids, list) and index < len(token_ids)
                else None
            )
            normalized_outcomes.append(
                MarketOutcome(
                    name=str(outcome).upper(),
                    price=_float_or_none(price),
                    token_id=str(token_id) if token_id else None,
                )
            )

    return Market(
        id=str(raw_market.get("conditionId") or raw_market.get("id") or ""),
        title=str(raw_market.get("question") or raw_market.get("title") or ""),
        slug=str(raw_market.get("slug") or ""),
        active=bool(raw_market.get("active", False)),
        closed=bool(raw_market.get("closed", False)),
        end_time=raw_market.get("endDate") or raw_market.get("endDateIso"),
        liquidity=_float_or_zero(raw_market.get("liquidity")),
        volume=_float_or_zero(raw_market.get("volume")),
        outcomes=normalized_outcomes,
        source="polymarket",
        metadata={
            "category": raw_market.get("category"),
            "tags": _tag_labels(raw_market),
        },
    )


def _raw_markets_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("markets"), list):
            return payload["markets"]
        if isinstance(payload.get("data"), list):
            return payload["data"]
    raise ValueError("markets response must be a list or contain markets/data list")


class PolymarketClient:
    def __init__(
        self,
        base_url: str = "https://gamma-api.polymarket.com",
        attempts: int = 2,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.attempts = max(1, attempts)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)

    def fetch_markets(self, limit: int = 50, active: bool = True) -> list[Market]:
        requested_limit = max(1, min(limit, 500))
        fetch_limit = min(max(requested_limit * 10, requested_limit), 500)
        params = urllib.parse.urlencode(
            {
                "limit": fetch_limit,
                "active": str(active).lower(),
                "closed": "false",
                "order": "volume",
                "ascending": "false",
            }
        )
        url = f"{self.base_url}/markets?{params}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "sports-edge-scanner/0.1.0"},
        )
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                raw_markets = _raw_markets_from_payload(payload)
                break
            except Exception as exc:
                last_error = exc
                if attempt < self.attempts - 1:
                    time.sleep(self.retry_delay_seconds)
        else:
            assert last_error is not None
            raise last_error

        markets: list[Market] = []
        for raw_market in raw_markets:
            if isinstance(raw_market, dict) and is_sports_market(raw_market):
                markets.append(normalize_market(raw_market))
                if len(markets) >= requested_limit:
                    break
        return markets
