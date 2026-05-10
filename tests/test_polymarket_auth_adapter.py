import json

import pytest

from sports_edge_scanner.connectors.polymarket_auth import (
    GeoblockStatus,
    PolymarketAuthenticatedExecutionClient,
    PolymarketCredentials,
    PolymarketGeoblockClient,
    map_execution_order_to_polymarket_args,
)
from sports_edge_scanner.core.execution import ExecutionOrder


def order(**overrides):
    values = {
        "client_order_id": "client-1",
        "market_id": "m1",
        "market_slug": "market-1",
        "outcome_name": "Team A",
        "token_id": "token-a",
        "side": "BUY",
        "order_type": "LIMIT",
        "limit_price": 0.5,
        "notional": 10.0,
        "time_in_force": "IOC",
        "source_signal_id": "signal-1",
        "created_at": "2026-05-10T00:00:00+00:00",
        "venue": "polymarket",
    }
    values.update(overrides)
    return ExecutionOrder(**values)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_geoblock_client_normalizes_status(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"blocked": True, "country": "US"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    status = PolymarketGeoblockClient().check()

    assert status == GeoblockStatus(
        blocked=True,
        country="US",
        raw={"blocked": True, "country": "US"},
    )


def test_order_mapper_converts_valid_order_to_sdk_args():
    args = map_execution_order_to_polymarket_args(order())

    assert args == {
        "token_id": "token-a",
        "side": "BUY",
        "price": 0.5,
        "size": 20.0,
        "time_in_force": "IOC",
        "client_order_id": "client-1",
    }


def test_order_mapper_rejects_unsupported_order_type():
    with pytest.raises(ValueError, match="unsupported order type"):
        map_execution_order_to_polymarket_args(order(order_type="LIMIT_MAKER"))


class FakeCredentialProvider:
    def load(self):
        return PolymarketCredentials(
            private_key="private",
            api_key="key",
            api_secret="secret",
            api_passphrase="pass",
            funder="0xfunder",
            signature_type=0,
        )


class FakeGeoblockClient:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def check(self):
        return GeoblockStatus(
            blocked=self.blocked,
            country="US" if self.blocked else "",
            raw={},
        )


class FakeSdkClient:
    def __init__(self):
        self.orders = []
        self.cancels = []

    def post_order(self, **kwargs):
        self.orders.append(kwargs)
        return {"orderID": "venue-1", "status": "open"}

    def cancel(self, order_id):
        self.cancels.append(order_id)
        return {"canceled": [order_id]}

    def get_order(self, order_id):
        return {"id": order_id, "status": "open"}


def test_authenticated_client_rejects_when_live_writes_disabled():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=False,
    )

    result = client.place_order(order())

    assert result.status == "live_writes_disabled"
    assert sdk.orders == []


def test_authenticated_client_rejects_when_geoblocked():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(blocked=True),
        allow_live_writes=True,
    )

    result = client.place_order(order())

    assert result.status == "geoblocked"
    assert sdk.orders == []


def test_authenticated_client_normalizes_sdk_success():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=True,
    )

    result = client.place_order(order())

    assert result.status == "open"
    assert result.venue_order_id == "venue-1"
    assert result.raw == {"sdk_status": "open"}
    assert sdk.orders[0]["token_id"] == "token-a"


def test_authenticated_client_sanitizes_sdk_exception():
    class ExplodingSdk(FakeSdkClient):
        def post_order(self, **kwargs):
            raise RuntimeError("secret private key leaked")

    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: ExplodingSdk(),
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=True,
    )

    result = client.place_order(order())

    assert result.status == "sdk_error"
    assert "secret" not in result.message
    assert "private" not in result.message


def test_authenticated_client_cancel_and_get_order_normalize_responses():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=True,
    )

    cancel = client.cancel_order("venue-1")
    status = client.get_order("venue-1")

    assert cancel.status == "canceled"
    assert status.status == "open"
