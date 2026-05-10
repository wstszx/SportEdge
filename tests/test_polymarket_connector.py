import json
from io import BytesIO

from sports_edge_scanner.connectors.polymarket import PolymarketClient, is_sports_market


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return BytesIO(self._payload)

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_fetch_markets_normalizes_gamma_response(monkeypatch):
    payload = [
        {
            "id": "123",
            "question": "Will Team A beat Team B?",
            "slug": "team-a-team-b",
            "active": True,
            "closed": False,
            "endDate": "2026-06-01T00:00:00Z",
            "liquidity": "1234.5",
            "volume": "9876.5",
            "outcomes": '["YES", "NO"]',
            "outcomePrices": '["0.47", "0.52"]',
            "clobTokenIds": '["yes-token", "no-token"]',
            "category": "Sports",
            "tags": [{"label": "NBA"}],
        }
    ]

    def fake_urlopen(request, timeout):
        return FakeResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketClient().fetch_markets(limit=1)

    assert len(markets) == 1
    assert markets[0].title == "Will Team A beat Team B?"
    assert markets[0].outcomes[0].name == "YES"
    assert markets[0].outcomes[0].price == 0.47
    assert markets[0].outcomes[0].token_id == "yes-token"
    assert markets[0].source == "polymarket"


def test_fetch_markets_keeps_filtering_until_requested_sports_limit(monkeypatch):
    payload = [
        {
            "id": "not-sports",
            "question": "Will it rain tomorrow?",
            "active": True,
            "closed": False,
            "outcomes": '["YES", "NO"]',
            "outcomePrices": '["0.47", "0.52"]',
        },
        {
            "id": "sports",
            "question": "Will the Lakers win?",
            "active": True,
            "closed": False,
            "outcomes": '["YES", "NO"]',
            "outcomePrices": '["0.47", "0.52"]',
        },
    ]

    def fake_urlopen(request, timeout):
        return FakeResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketClient().fetch_markets(limit=1)

    assert len(markets) == 1
    assert markets[0].id == "sports"


def test_is_sports_market_uses_category_tags_and_title_keywords():
    assert is_sports_market({"category": "Sports", "question": "Unrelated"}) is True
    assert is_sports_market({"tags": [{"label": "NBA"}], "question": "Market"}) is True
    assert is_sports_market({"question": "Will Arsenal win?"}) is True
    assert is_sports_market({"question": "Will it rain tomorrow?"}) is False


def test_fetch_markets_retries_after_transient_failure(monkeypatch):
    calls = {"count": 0}
    payload = [
        {
            "id": "sports",
            "question": "Will the Lakers win?",
            "active": True,
            "closed": False,
            "outcomes": '["YES", "NO"]',
            "outcomePrices": '["0.47", "0.52"]',
        }
    ]

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary network error")
        return FakeResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketClient(retry_delay_seconds=0.0).fetch_markets(limit=1)

    assert calls["count"] == 2
    assert len(markets) == 1


def test_fetch_markets_rejects_invalid_payload_shape(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"unexpected": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    try:
        PolymarketClient(retry_delay_seconds=0.0).fetch_markets(limit=1)
        raised = False
    except ValueError as exc:
        raised = "markets response" in str(exc)

    assert raised is True
