import json

import pytest

from sports_edge_scanner.connectors.polymarket_auth import (
    GeoblockStatus,
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
