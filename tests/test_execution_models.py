import pytest

from sports_edge_scanner.core.execution import (
    DryRunExecutionClient,
    ExecutionOrder,
)


def valid_order(**overrides):
    values = {
        "client_order_id": "client-1",
        "market_id": "m1",
        "market_slug": "market-1",
        "outcome_name": "Team A",
        "token_id": "token-a",
        "side": "BUY",
        "order_type": "LIMIT",
        "limit_price": 0.47,
        "notional": 10.0,
        "time_in_force": "IOC",
        "source_signal_id": "signal-1",
        "created_at": "2026-05-10T00:00:00+00:00",
        "venue": "polymarket",
    }
    values.update(overrides)
    return ExecutionOrder(**values)


def test_execution_order_to_dict_contains_required_fields():
    order = valid_order()

    assert order.to_dict()["client_order_id"] == "client-1"
    assert order.to_dict()["side"] == "BUY"
    assert order.to_dict()["venue"] == "polymarket"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"client_order_id": ""}, "client_order_id is required"),
        ({"market_id": ""}, "market_id is required"),
        ({"token_id": ""}, "token_id is required"),
        ({"side": "HOLD"}, "side must be BUY or SELL"),
        ({"order_type": "MARKET"}, "order_type must start with LIMIT"),
        ({"limit_price": 0.0}, "limit_price must be greater than 0 and less than 1"),
        ({"limit_price": 1.0}, "limit_price must be greater than 0 and less than 1"),
        ({"notional": 0.0}, "notional must be positive"),
    ],
)
def test_execution_order_validation_rejects_unsafe_values(overrides, message):
    with pytest.raises(ValueError, match=message):
        valid_order(**overrides)


def test_dry_run_execution_client_returns_deterministic_result():
    client = DryRunExecutionClient()

    result = client.place_order(valid_order())

    assert result.client_order_id == "client-1"
    assert result.venue_order_id == "dry-run-client-1"
    assert result.status == "dry_run_accepted"
    assert result.filled_notional == 0.0
    assert result.remaining_notional == 10.0
    assert result.to_dict()["message"] == "dry-run only; no venue order was sent"
