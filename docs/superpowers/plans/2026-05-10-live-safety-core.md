# Live Safety Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a venue-neutral live execution safety layer that only supports audited dry-run execution in this phase.

**Architecture:** Add a focused `sports_edge_scanner.core.execution` module for execution models, dry-run client, live-mode config, guard decisions, audit orchestration, and config templates. Wire a new `live` CLI group to those pure helpers while keeping all authenticated trading, private keys, signing, and real venue endpoints out of scope.

**Tech Stack:** Python 3.10+, dataclasses, pathlib/json, existing JSONL event helpers, pytest.

---

## File Structure

- Create `sports_edge_scanner/core/execution.py`: execution dataclasses, validation, `ExecutionClient` protocol, `DryRunExecutionClient`, `LiveModeConfig`, `GuardDecision`, `LiveModeGuard`, config load/write helpers, and `run_dry_run_execution`.
- Modify `sports_edge_scanner/cli.py`: add `live init-config`, `live check-config`, and `live dry-run` commands.
- Modify `README.md`: describe the live-safety dry-run phase and explicitly say it still cannot place real orders.
- Create `tests/test_execution_models.py`: order validation and dry-run client tests.
- Create `tests/test_live_guard.py`: live-mode guard rejection and approval tests.
- Create `tests/test_live_cli.py`: parser/config/dry-run audit tests.

## Task 1: Execution Models And Dry-Run Client

**Files:**
- Create: `tests/test_execution_models.py`
- Create: `sports_edge_scanner/core/execution.py`

- [ ] **Step 1: Write failing model and dry-run tests**

Create `tests/test_execution_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_execution_models.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'sports_edge_scanner.core.execution'`.

- [ ] **Step 3: Implement minimal execution models and dry-run client**

Create `sports_edge_scanner/core/execution.py`:

```python
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class ExecutionOrder:
    client_order_id: str
    market_id: str
    market_slug: str
    outcome_name: str
    token_id: str
    side: str
    order_type: str
    limit_price: float
    notional: float
    time_in_force: str
    source_signal_id: str
    created_at: str
    venue: str = "polymarket"

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id is required")
        if not self.market_id:
            raise ValueError("market_id is required")
        if not self.token_id:
            raise ValueError("token_id is required")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if not self.order_type.startswith("LIMIT"):
            raise ValueError("order_type must start with LIMIT")
        if self.limit_price <= 0.0 or self.limit_price >= 1.0:
            raise ValueError("limit_price must be greater than 0 and less than 1")
        if self.notional <= 0.0:
            raise ValueError("notional must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    client_order_id: str
    venue_order_id: str
    status: str
    filled_notional: float
    remaining_notional: float
    average_price: float | None
    message: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionOrderStatus:
    client_order_id: str
    venue_order_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionClient(Protocol):
    def place_order(self, order: ExecutionOrder) -> ExecutionResult:
        ...

    def cancel_order(self, order_id: str) -> ExecutionResult:
        ...

    def get_order(self, order_id: str) -> ExecutionOrderStatus:
        ...


class DryRunExecutionClient:
    def place_order(self, order: ExecutionOrder) -> ExecutionResult:
        return ExecutionResult(
            client_order_id=order.client_order_id,
            venue_order_id=f"dry-run-{order.client_order_id}",
            status="dry_run_accepted",
            filled_notional=0.0,
            remaining_notional=order.notional,
            average_price=None,
            message="dry-run only; no venue order was sent",
            raw={"venue": order.venue},
        )

    def cancel_order(self, order_id: str) -> ExecutionResult:
        return ExecutionResult(
            client_order_id=order_id,
            venue_order_id=f"dry-run-{order_id}",
            status="dry_run_cancel_accepted",
            filled_notional=0.0,
            remaining_notional=0.0,
            average_price=None,
            message="dry-run only; no venue cancel was sent",
            raw={},
        )

    def get_order(self, order_id: str) -> ExecutionOrderStatus:
        return ExecutionOrderStatus(
            client_order_id=order_id,
            venue_order_id=f"dry-run-{order_id}",
            status="dry_run_unknown",
            raw={},
        )
```

- [ ] **Step 4: Run model tests**

Run: `python -m pytest tests/test_execution_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/execution.py tests/test_execution_models.py
git commit -m "feat: add execution models"
```

## Task 2: Live Mode Config And Guard

**Files:**
- Modify: `sports_edge_scanner/core/execution.py`
- Create: `tests/test_live_guard.py`

- [ ] **Step 1: Write failing guard tests**

Create `tests/test_live_guard.py`:

```python
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


def test_live_guard_rejects_live_mode_in_this_phase():
    decision = LiveModeGuard(
        dry_run_config(mode="live", live_enabled=True, kill_switch_enabled=False)
    ).evaluate(order(), allowed_risk(), confirmation_token="confirm-live-dry-run")

    assert decision.allowed is False
    assert "live mode is not implemented" in decision.reasons


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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_live_guard.py -q`

Expected: FAIL because `LiveModeConfig` and `LiveModeGuard` do not exist.

- [ ] **Step 3: Implement config, guard decision, and guard**

Append to `sports_edge_scanner/core/execution.py`:

```python
@dataclass(frozen=True)
class LiveModeConfig:
    mode: str = "dry_run"
    live_enabled: bool = False
    require_confirmation_token: bool = True
    confirmation_token: str = "confirm-live-dry-run"
    kill_switch_enabled: bool = True
    max_order_notional: float = 10.0
    max_market_exposure: float = 25.0
    max_total_exposure: float = 100.0
    daily_loss_limit: float = 25.0
    allowed_venues: list[str] = field(default_factory=lambda: ["polymarket"])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reasons: list[str]
    mode: str
    requested_notional: float
    approved_notional: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveModeGuard:
    def __init__(self, config: LiveModeConfig) -> None:
        self.config = config

    def evaluate(
        self,
        order: ExecutionOrder,
        risk_decision,
        confirmation_token: str = "",
    ) -> GuardDecision:
        reasons: list[str] = []
        approved_notional = min(order.notional, risk_decision.approved_notional)

        if self.config.kill_switch_enabled:
            reasons.append("kill switch enabled")
        if self.config.mode not in {"dry_run", "live"}:
            reasons.append("unknown live mode")
        if self.config.mode == "live" and not self.config.live_enabled:
            reasons.append("live mode disabled")
        if self.config.mode == "live":
            reasons.append("live mode is not implemented")
        if (
            self.config.require_confirmation_token
            and confirmation_token != self.config.confirmation_token
        ):
            reasons.append("confirmation token mismatch")
        if order.venue not in self.config.allowed_venues:
            reasons.append("venue not allowed")
        if not risk_decision.allowed:
            reasons.append("risk decision rejected")
        if order.notional > self.config.max_order_notional:
            reasons.append("max_order_notional exceeded")
        if approved_notional <= 0.0:
            reasons.append("no approved notional")

        allowed = not reasons and self.config.mode == "dry_run"
        if allowed:
            reasons.append("allowed dry-run execution")

        return GuardDecision(
            allowed=allowed,
            reasons=reasons,
            mode=self.config.mode,
            requested_notional=order.notional,
            approved_notional=approved_notional if allowed else 0.0,
        )
```

- [ ] **Step 4: Run guard tests**

Run: `python -m pytest tests/test_live_guard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/execution.py tests/test_live_guard.py
git commit -m "feat: add live mode guard"
```

## Task 3: Config Helpers And Audited Dry-Run Pipeline

**Files:**
- Modify: `sports_edge_scanner/core/execution.py`
- Create: `tests/test_live_cli.py`

- [ ] **Step 1: Write failing config and audit tests**

Create `tests/test_live_cli.py`:

```python
import json

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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_live_cli.py -q`

Expected: FAIL because config helpers and `run_dry_run_execution` do not exist.

- [ ] **Step 3: Implement config helpers and audited dry-run**

Append to `sports_edge_scanner/core/execution.py`:

```python
import json

from sports_edge_scanner.core.events import append_event, make_event


def write_live_config_template(path: Path, force: bool = False) -> Path:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(LiveModeConfig().to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_live_mode_config(path: Path) -> LiveModeConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return LiveModeConfig(**payload)


def _rejected_result(order: ExecutionOrder, decision: GuardDecision) -> ExecutionResult:
    return ExecutionResult(
        client_order_id=order.client_order_id,
        venue_order_id="",
        status="rejected",
        filled_notional=0.0,
        remaining_notional=order.notional,
        average_price=None,
        message=", ".join(decision.reasons),
        raw={"guard_decision": decision.to_dict()},
    )


def run_dry_run_execution(
    execution_client: ExecutionClient,
    guard: LiveModeGuard,
    order: ExecutionOrder,
    risk_decision,
    events_path: Path,
    run_id: str,
    confirmation_token: str = "",
) -> ExecutionResult:
    append_event(events_path, make_event("execution_intent", run_id, order.to_dict()))
    decision = guard.evaluate(order, risk_decision, confirmation_token=confirmation_token)
    append_event(
        events_path,
        make_event("live_guard_decision", run_id, decision.to_dict()),
    )

    if not decision.allowed:
        result = _rejected_result(order, decision)
        append_event(
            events_path,
            make_event("execution_rejected", run_id, result.to_dict()),
        )
        return result

    result = execution_client.place_order(order)
    append_event(events_path, make_event("execution_dry_run", run_id, result.to_dict()))
    append_event(events_path, make_event("execution_result", run_id, result.to_dict()))
    return result
```

- [ ] **Step 4: Run live CLI support tests**

Run: `python -m pytest tests/test_live_cli.py -q`

Expected: PASS for helper tests.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/execution.py tests/test_live_cli.py
git commit -m "feat: add audited dry-run execution"
```

## Task 4: Live CLI Commands

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_live_cli.py`

- [ ] **Step 1: Add failing CLI parser and command tests**

Append to `tests/test_live_cli.py`:

```python
from sports_edge_scanner.cli import build_parser, main


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

    assert init_args.command == "live"
    assert init_args.live_command == "init-config"
    assert check_args.live_command == "check-config"
    assert dry_args.live_command == "dry-run"


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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_live_cli.py -q`

Expected: FAIL because `live` parser commands do not exist.

- [ ] **Step 3: Add CLI imports and helper**

Modify `sports_edge_scanner/cli.py` imports:

```python
from datetime import datetime, timezone
```

Add execution imports:

```python
from sports_edge_scanner.core.execution import (
    DryRunExecutionClient,
    ExecutionOrder,
    LiveModeConfig,
    LiveModeGuard,
    load_live_mode_config,
    run_dry_run_execution,
    write_live_config_template,
)
```

Add helper functions above `build_parser`:

```python
def _load_live_config(path_value: str) -> LiveModeConfig:
    if not path_value:
        return LiveModeConfig()
    return load_live_mode_config(Path(path_value))


def _sample_execution_order() -> ExecutionOrder:
    return ExecutionOrder(
        client_order_id=str(uuid4()),
        market_id="dry-run-market",
        market_slug="dry-run-market",
        outcome_name="DRY_RUN",
        token_id="dry-run-token",
        side="BUY",
        order_type="LIMIT",
        limit_price=0.5,
        notional=1.0,
        time_in_force="IOC",
        source_signal_id="manual-dry-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        venue="polymarket",
    )
```

- [ ] **Step 4: Add live command handlers**

Add above `build_parser`:

```python
def _live_init_config(args: argparse.Namespace) -> int:
    try:
        path = write_live_config_template(Path(args.config), force=args.force)
    except FileExistsError as exc:
        print(f"live init-config failed: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


def _live_check_config(args: argparse.Namespace) -> int:
    try:
        config = load_live_mode_config(Path(args.config))
    except Exception as exc:
        print(f"live check-config failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(config.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Mode: {config.mode}")
        print(f"Live enabled: {config.live_enabled}")
        print(f"Kill switch enabled: {config.kill_switch_enabled}")
    return 1 if config.kill_switch_enabled or config.mode != "dry_run" else 0


def _live_dry_run(args: argparse.Namespace) -> int:
    risk_decision = RiskDecision(
        allowed=True,
        reasons=["allowed"],
        requested_notional=1.0,
        approved_notional=1.0,
    )
    try:
        result = run_dry_run_execution(
            execution_client=DryRunExecutionClient(),
            guard=LiveModeGuard(_load_live_config(args.config)),
            order=_sample_execution_order(),
            risk_decision=risk_decision,
            events_path=Path(args.events),
            run_id=str(uuid4()),
            confirmation_token=args.confirm_token,
        )
    except Exception as exc:
        print(f"live dry-run failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Status: {result.status}")
        print(f"Message: {result.message}")
        print(f"Events: {args.events}")
    return 0 if result.status == "dry_run_accepted" else 1
```

- [ ] **Step 5: Add parser group**

Inside `build_parser`, before `return parser`:

```python
live = subparsers.add_parser("live", help="Inspect live-trading safety controls.")
live_subparsers = live.add_subparsers(dest="live_command", required=True)

live_init = live_subparsers.add_parser(
    "init-config",
    help="Write a safe live-mode config template.",
)
live_init.add_argument("--config", default="live_config.json")
live_init.add_argument("--force", action="store_true")
live_init.set_defaults(func=_live_init_config)

live_check = live_subparsers.add_parser(
    "check-config",
    help="Check whether live-mode config is safely gated.",
)
live_check.add_argument("--config", default="live_config.json")
live_check.add_argument("--json", action="store_true")
live_check.set_defaults(func=_live_check_config)

live_dry_run = live_subparsers.add_parser(
    "dry-run",
    help="Run an audited dry-run through the live safety guard.",
)
live_dry_run.add_argument("--config", default="")
live_dry_run.add_argument("--events", default="execution_events.jsonl")
live_dry_run.add_argument("--confirm-token", default="")
live_dry_run.add_argument("--json", action="store_true")
live_dry_run.set_defaults(func=_live_dry_run)
```

- [ ] **Step 6: Run live CLI tests**

Run: `python -m pytest tests/test_live_cli.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add sports_edge_scanner/cli.py tests/test_live_cli.py
git commit -m "feat: add live safety cli"
```

## Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README section**

Append after Shadow Trading Simulation:

```markdown
## Live Safety Core

The `live` command group is a safety scaffold for future real execution. In this phase it still does not place real orders, cancel orders, sign payloads, load private keys, or manage wallets.

Create the safe default config:

```bash
python -m sports_edge_scanner live init-config
```

Check the config:

```bash
python -m sports_edge_scanner live check-config --config live_config.json
```

Run an audited dry-run through the live safety guard:

```bash
python -m sports_edge_scanner live dry-run --events execution_events.jsonl --confirm-token confirm-live-dry-run
```

The default config keeps the kill switch enabled, so dry-run execution is rejected until the operator explicitly disables it in a local config file. Real venue execution requires a later authenticated adapter design.
```

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_execution_models.py tests/test_live_guard.py tests/test_live_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 5: Run local command checks**

Run:

```bash
python -m sports_edge_scanner live init-config --config tmp_live_config.json --force
python -m sports_edge_scanner live check-config --config tmp_live_config.json --json
python -m sports_edge_scanner live dry-run --events tmp_execution_events.jsonl --confirm-token confirm-live-dry-run --json
```

Expected:

- `init-config` exits 0.
- `check-config` exits 1 because the kill switch is enabled by default.
- `dry-run` exits 1 and writes rejection audit events because the default config is safe.

Delete the temporary files after inspection:

```powershell
Remove-Item -LiteralPath tmp_live_config.json,tmp_execution_events.jsonl -ErrorAction SilentlyContinue
```

- [ ] **Step 6: Review diff**

Run: `git diff --stat`

Expected: only execution core, CLI, tests, README, spec, and plan files changed.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: document live safety core"
```
