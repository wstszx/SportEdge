from dataclasses import asdict, dataclass, field
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
