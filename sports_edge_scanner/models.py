from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class MarketOutcome:
    name: str
    price: Optional[float] = None
    token_id: Optional[str] = None


@dataclass(frozen=True)
class Market:
    id: str
    title: str
    slug: str
    active: bool
    closed: bool
    end_time: Optional[str]
    liquidity: float
    volume: float
    outcomes: list[MarketOutcome]
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Signal:
    market_id: str
    title: str
    status: str
    reasons: list[str]
    side: Optional[str] = None
    price: Optional[float] = None
    fair_probability: Optional[float] = None
    break_even_probability: Optional[float] = None
    edge: Optional[float] = None
    kelly_fraction: Optional[float] = None
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    size: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderBook:
    market_id: str
    token_id: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: str
    tick_size: Optional[float] = None
    source: str = "polymarket_clob"

    @property
    def best_bid(self) -> Optional[float]:
        if not self.bids:
            return None
        return max(level.price for level in self.bids)

    @property
    def best_ask(self) -> Optional[float]:
        if not self.asks:
            return None
        return min(level.price for level in self.asks)

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return max(0.0, self.best_ask - self.best_bid)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_id": self.market_id,
            "token_id": self.token_id,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "timestamp": self.timestamp,
            "tick_size": self.tick_size,
            "source": self.source,
        }


@dataclass(frozen=True)
class CandidateOrder:
    market_id: str
    market_slug: str
    outcome_name: str
    token_id: str
    side: str
    limit_price: float
    requested_notional: float
    fair_probability: float
    edge: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: list[str]
    requested_notional: float
    approved_notional: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowOrder:
    order_id: str
    market_id: str
    outcome_name: str
    token_id: str
    side: str
    limit_price: float
    notional: float
    source_signal_id: str
    time_in_force: str = "IOC"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowFill:
    order_id: str
    status: str
    requested_notional: float
    filled_notional: float
    filled_contracts: float
    average_price: Optional[float]
    unfilled_notional: float
    slippage: float
    consumed_levels: list[dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
