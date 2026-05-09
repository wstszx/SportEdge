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
