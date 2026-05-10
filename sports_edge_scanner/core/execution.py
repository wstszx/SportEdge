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
