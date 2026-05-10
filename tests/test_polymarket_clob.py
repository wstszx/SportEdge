import json
from io import BytesIO

from sports_edge_scanner.connectors.polymarket_clob import (
    PolymarketCLOBClient,
    normalize_orderbook,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return BytesIO(self._payload)

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_normalize_orderbook_sorts_bid_and_ask_levels():
    payload = {
        "market": "market-1",
        "asset_id": "token-a",
        "bids": [{"price": "0.44", "size": "10"}, {"price": "0.45", "size": "5"}],
        "asks": [{"price": "0.48", "size": "5"}, {"price": "0.47", "size": "10"}],
        "timestamp": "2026-05-10T00:00:00+00:00",
    }

    book = normalize_orderbook(payload, fallback_token_id="token-a")

    assert book.market_id == "market-1"
    assert book.token_id == "token-a"
    assert [level.price for level in book.bids] == [0.45, 0.44]
    assert [level.price for level in book.asks] == [0.47, 0.48]


def test_fetch_orderbook_uses_token_id_parameter(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(
            {
                "market": "market-1",
                "asset_id": "token-a",
                "bids": [{"price": "0.44", "size": "10"}],
                "asks": [{"price": "0.47", "size": "10"}],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    book = PolymarketCLOBClient(base_url="https://clob.polymarket.com").fetch_orderbook(
        "token-a"
    )

    assert "token_id=token-a" in captured["url"]
    assert book.best_ask == 0.47
