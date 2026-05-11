import json

from sports_edge_scanner.cli import build_parser, main
from sports_edge_scanner.core.events import read_events
from sports_edge_scanner.core.execution import (
    DryRunExecutionClient,
    ExecutionOrder,
    LiveModeConfig,
    LiveModeGuard,
    load_live_mode_config,
    run_dry_run_execution,
    write_live_config_template,
)
from sports_edge_scanner.models import RiskDecision


def order():
    return ExecutionOrder(
        client_order_id="client-1",
        market_id="m1",
        market_slug="market-1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        order_type="LIMIT",
        limit_price=0.47,
        notional=10.0,
        time_in_force="IOC",
        source_signal_id="signal-1",
        created_at="2026-05-10T00:00:00+00:00",
        venue="polymarket",
    )


def risk(allowed=True):
    return RiskDecision(
        allowed=allowed,
        reasons=["allowed"] if allowed else ["wide spread"],
        requested_notional=10.0,
        approved_notional=10.0 if allowed else 0.0,
    )


def test_live_config_template_defaults_to_safe_rejection(tmp_path):
    path = tmp_path / "live_config.json"

    write_live_config_template(path)
    loaded = load_live_mode_config(path)

    assert loaded.mode == "dry_run"
    assert loaded.kill_switch_enabled is True
    assert loaded.live_enabled is False
    assert json.loads(path.read_text(encoding="utf-8"))["kill_switch_enabled"] is True


def test_run_dry_run_execution_writes_audit_events_for_success(tmp_path):
    events_path = tmp_path / "execution_events.jsonl"
    config = LiveModeConfig(kill_switch_enabled=False)

    result = run_dry_run_execution(
        execution_client=DryRunExecutionClient(),
        guard=LiveModeGuard(config),
        order=order(),
        risk_decision=risk(),
        events_path=events_path,
        run_id="run-1",
        confirmation_token="confirm-live-dry-run",
    )

    events = read_events(events_path)
    assert result.status == "dry_run_accepted"
    assert [event["event_type"] for event in events] == [
        "execution_intent",
        "live_guard_decision",
        "execution_dry_run",
        "execution_result",
    ]
    assert events[1]["allowed"] is True


def test_run_dry_run_execution_writes_rejection_event(tmp_path):
    events_path = tmp_path / "execution_events.jsonl"

    result = run_dry_run_execution(
        execution_client=DryRunExecutionClient(),
        guard=LiveModeGuard(LiveModeConfig()),
        order=order(),
        risk_decision=risk(),
        events_path=events_path,
        run_id="run-1",
        confirmation_token="confirm-live-dry-run",
    )

    events = read_events(events_path)
    assert result.status == "rejected"
    assert [event["event_type"] for event in events] == [
        "execution_intent",
        "live_guard_decision",
        "execution_rejected",
    ]
    assert "kill switch enabled" in events[1]["reasons"]


def test_parser_supports_live_commands():
    parser = build_parser()

    init_args = parser.parse_args(["live", "init-config", "--config", "live.json"])
    check_args = parser.parse_args(["live", "check-config", "--config", "live.json"])
    dry_args = parser.parse_args(
        [
            "live",
            "dry-run",
            "--events",
            "execution.jsonl",
            "--confirm-token",
            "confirm-live-dry-run",
        ]
    )
    run_args = parser.parse_args(
        [
            "live",
            "run",
            "--limit",
            "2",
            "--events",
            "execution.jsonl",
            "--live-config",
            "live.json",
            "--auth-config",
            "auth.json",
        ]
    )

    assert init_args.command == "live"
    assert init_args.live_command == "init-config"
    assert check_args.live_command == "check-config"
    assert dry_args.live_command == "dry-run"
    assert run_args.live_command == "run"
    assert run_args.limit == 2
    assert run_args.events == "execution.jsonl"
    assert run_args.live_config == "live.json"
    assert run_args.auth_config == "auth.json"


def test_live_init_and_check_config_commands(tmp_path):
    config_path = tmp_path / "live_config.json"

    assert main(["live", "init-config", "--config", str(config_path)]) == 0
    assert main(["live", "check-config", "--config", str(config_path)]) == 1


def test_live_dry_run_command_writes_rejection_events(tmp_path):
    events_path = tmp_path / "execution_events.jsonl"

    exit_code = main(
        [
            "live",
            "dry-run",
            "--events",
            str(events_path),
            "--confirm-token",
            "confirm-live-dry-run",
        ]
    )

    events = read_events(events_path)
    assert exit_code == 1
    assert "execution_rejected" in [event["event_type"] for event in events]


def test_live_run_command_rejects_without_enabled_configs(tmp_path):
    events_path = tmp_path / "execution_events.jsonl"

    exit_code = main(
        [
            "live",
            "run",
            "--events",
            str(events_path),
            "--limit",
            "1",
        ]
    )

    assert exit_code == 1
