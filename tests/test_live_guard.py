from sports_edge_scanner.core.execution import (
    ExecutionOrder,
    LiveModeConfig,
    LiveModeGuard,
)
from sports_edge_scanner.models import RiskDecision


def order(**overrides):
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


def allowed_risk(**overrides):
    values = {
        "allowed": True,
        "reasons": ["allowed"],
        "requested_notional": 10.0,
        "approved_notional": 10.0,
    }
    values.update(overrides)
    return RiskDecision(**values)


def dry_run_config(**overrides):
    values = {
        "mode": "dry_run",
        "live_enabled": False,
        "require_confirmation_token": True,
        "confirmation_token": "confirm-live-dry-run",
        "kill_switch_enabled": False,
        "max_order_notional": 10.0,
        "max_market_exposure": 25.0,
        "max_total_exposure": 100.0,
        "daily_loss_limit": 25.0,
        "allowed_venues": ["polymarket"],
    }
    values.update(overrides)
    return LiveModeConfig(**values)


def test_live_guard_rejects_when_kill_switch_enabled():
    decision = LiveModeGuard(dry_run_config(kill_switch_enabled=True)).evaluate(
        order(),
        allowed_risk(),
        confirmation_token="confirm-live-dry-run",
    )

    assert decision.allowed is False
    assert "kill switch enabled" in decision.reasons


def test_live_guard_approves_enabled_live_mode_when_safety_inputs_pass():
    decision = LiveModeGuard(
        dry_run_config(mode="live", live_enabled=True, kill_switch_enabled=False)
    ).evaluate(order(), allowed_risk(), confirmation_token="confirm-live-dry-run")

    assert decision.allowed is True
    assert decision.approved_notional == 10.0
    assert decision.reasons == ["allowed live execution"]


def test_live_guard_rejects_missing_confirmation_token():
    decision = LiveModeGuard(dry_run_config()).evaluate(
        order(),
        allowed_risk(),
        confirmation_token="",
    )

    assert decision.allowed is False
    assert "confirmation token mismatch" in decision.reasons


def test_live_guard_rejects_disallowed_venue_and_risk_decision():
    decision = LiveModeGuard(dry_run_config(allowed_venues=["other"])).evaluate(
        order(),
        allowed_risk(allowed=False, reasons=["wide spread"], approved_notional=0.0),
        confirmation_token="confirm-live-dry-run",
    )

    assert decision.allowed is False
    assert "venue not allowed" in decision.reasons
    assert "risk decision rejected" in decision.reasons


def test_live_guard_approves_valid_dry_run():
    decision = LiveModeGuard(dry_run_config()).evaluate(
        order(),
        allowed_risk(),
        confirmation_token="confirm-live-dry-run",
    )

    assert decision.allowed is True
    assert decision.approved_notional == 10.0
    assert decision.reasons == ["allowed dry-run execution"]
