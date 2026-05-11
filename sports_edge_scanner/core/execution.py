import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from sports_edge_scanner.core.auto_fair import AutoFairConfig
from sports_edge_scanner.core.events import append_event, make_event
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig
from sports_edge_scanner.core.trade_pipeline import run_trade_scan


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

        allowed = not reasons and self.config.mode in {"dry_run", "live"}
        if allowed:
            if self.config.mode == "live":
                reasons.append("allowed live execution")
            else:
                reasons.append("allowed dry-run execution")

        return GuardDecision(
            allowed=allowed,
            reasons=reasons,
            mode=self.config.mode,
            requested_notional=order.notional,
            approved_notional=approved_notional if allowed else 0.0,
        )


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


def run_execution(
    execution_client: ExecutionClient,
    guard: LiveModeGuard,
    order: ExecutionOrder,
    risk_decision,
    events_path: Path,
    run_id: str,
    confirmation_token: str = "",
    accepted_event_type: str = "execution_result",
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
    append_event(events_path, make_event(accepted_event_type, run_id, result.to_dict()))
    append_event(events_path, make_event("execution_result", run_id, result.to_dict()))
    return result


def run_dry_run_execution(
    execution_client: ExecutionClient,
    guard: LiveModeGuard,
    order: ExecutionOrder,
    risk_decision,
    events_path: Path,
    run_id: str,
    confirmation_token: str = "",
) -> ExecutionResult:
    return run_execution(
        execution_client=execution_client,
        guard=guard,
        order=order,
        risk_decision=risk_decision,
        events_path=events_path,
        run_id=run_id,
        confirmation_token=confirmation_token,
        accepted_event_type="execution_dry_run",
    )


def _execution_order_id(run_id: str, index: int) -> str:
    return f"{run_id}-live-{index}"


def run_live_scan(
    market_client: Any,
    book_client: Any,
    fair_book: FairProbabilityBook | None,
    risk_config: RiskConfig,
    live_config: LiveModeConfig,
    execution_client: ExecutionClient,
    limit: int,
    events_path: Path,
    run_id: str,
    now: datetime | None = None,
    auto_fair_config: AutoFairConfig | None = None,
    confirmation_token: str = "",
) -> dict[str, object]:
    guard = LiveModeGuard(live_config)

    def on_accepted_order(candidate, decision, book, order_index, current_time):
        order = ExecutionOrder(
            client_order_id=_execution_order_id(run_id, order_index),
            market_id=candidate.market_id,
            market_slug=candidate.market_slug,
            outcome_name=candidate.outcome_name,
            token_id=candidate.token_id,
            side="BUY",
            order_type="LIMIT",
            limit_price=candidate.limit_price,
            notional=decision.approved_notional,
            time_in_force="IOC",
            source_signal_id=f"{run_id}-signal-{order_index}",
            created_at=current_time.isoformat(),
            venue="polymarket",
        )
        result = run_execution(
            execution_client=execution_client,
            guard=guard,
            order=order,
            risk_decision=decision,
            events_path=events_path,
            run_id=run_id,
            confirmation_token=confirmation_token,
            accepted_event_type="execution_order",
        )
        if result.status == "rejected":
            return {
                "accepted": False,
                "counts": {"execution_rejected_count": 1},
            }
        return {
            "accepted": True,
            "counts": {"execution_submitted_count": 1},
        }

    summary = run_trade_scan(
        market_client=market_client,
        book_client=book_client,
        fair_book=fair_book,
        risk_config=risk_config,
        limit=limit,
        events_path=events_path,
        run_id=run_id,
        order_id_suffix="live",
        on_accepted_order=on_accepted_order,
        now=now,
        auto_fair_config=auto_fair_config,
    )
    summary.setdefault("execution_submitted_count", 0)
    summary.setdefault("execution_rejected_count", 0)
    return summary
