# Shadow Trading Reliability Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a REST-backed shadow trading pipeline that simulates live order decisions, risk checks, and fills without real order placement or credentials.

**Architecture:** Keep existing research commands compatible while adding generic outcome handling, public CLOB orderbooks, pure risk and execution modules, append-only shadow events, and report aggregation. Network clients stay thin and all trading behavior is implemented in deterministic pure functions with mocked integration tests.

**Tech Stack:** Python 3.10+, standard library `argparse`, `dataclasses`, `json`, `pathlib`, `urllib`; `pytest` for tests.

---

## File Structure

- Modify `sports_edge_scanner/models.py`: add orderbook, candidate, risk, shadow order, and shadow fill dataclasses.
- Create `sports_edge_scanner/core/fair.py`: load and match fair probabilities by token, market id, slug, and outcome name.
- Create `sports_edge_scanner/connectors/polymarket_clob.py`: fetch public CLOB token orderbooks and normalize levels.
- Create `sports_edge_scanner/core/shadow_signals.py`: generate buy-side candidate orders from markets, fair probabilities, and orderbooks.
- Create `sports_edge_scanner/core/risk.py`: apply conservative risk limits and size reductions.
- Create `sports_edge_scanner/core/shadow_execution.py`: simulate buy limit fills by walking ask levels.
- Create `sports_edge_scanner/core/events.py`: append/read schema-versioned JSONL events.
- Create `sports_edge_scanner/core/shadow_reports.py`: aggregate shadow events into execution and risk summaries.
- Modify `sports_edge_scanner/cli.py`: add `shadow scan` and `shadow report` commands.
- Modify `README.md`: document shadow mode and its safety boundary.
- Add tests for each new module plus mocked CLI integration.

## Task 1: Shadow Models

**Files:**
- Modify: `sports_edge_scanner/models.py`
- Test: `tests/test_shadow_models.py`

- [ ] **Step 1: Write failing tests for model serialization**

Create `tests/test_shadow_models.py`:

```python
from sports_edge_scanner.models import (
    CandidateOrder,
    OrderBook,
    OrderBookLevel,
    RiskDecision,
    ShadowFill,
    ShadowOrder,
)


def test_orderbook_best_bid_ask_and_spread():
    book = OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.44, size=100.0)],
        asks=[OrderBookLevel(price=0.46, size=50.0)],
        timestamp="2026-05-10T00:00:00+00:00",
    )

    assert book.best_bid == 0.44
    assert book.best_ask == 0.46
    assert book.spread == 0.02


def test_candidate_risk_order_and_fill_to_dicts():
    candidate = CandidateOrder(
        market_id="m1",
        market_slug="team-a-win",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=0.47,
        requested_notional=10.0,
        fair_probability=0.55,
        edge=0.08,
        reason="fair probability clears executable price",
    )
    decision = RiskDecision(
        allowed=True,
        reasons=["allowed"],
        requested_notional=10.0,
        approved_notional=8.0,
    )
    order = ShadowOrder(
        order_id="shadow-1",
        market_id="m1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=0.47,
        notional=8.0,
        source_signal_id="signal-1",
    )
    fill = ShadowFill(
        order_id="shadow-1",
        status="partial",
        requested_notional=8.0,
        filled_notional=5.0,
        filled_contracts=10.0,
        average_price=0.5,
        unfilled_notional=3.0,
        slippage=0.03,
        consumed_levels=[{"price": 0.5, "notional": 5.0, "contracts": 10.0}],
    )

    assert candidate.to_dict()["outcome_name"] == "Team A"
    assert decision.to_dict()["approved_notional"] == 8.0
    assert order.to_dict()["order_id"] == "shadow-1"
    assert fill.to_dict()["status"] == "partial"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_shadow_models.py -q`

Expected: FAIL because the shadow dataclasses do not exist.

- [ ] **Step 3: Implement shadow dataclasses**

Append these dataclasses to `sports_edge_scanner/models.py`:

```python
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
```

- [ ] **Step 4: Run model tests**

Run: `python -m pytest tests/test_shadow_models.py -q`

Expected: PASS.

## Task 2: Fair Probability Matching

**Files:**
- Create: `sports_edge_scanner/core/fair.py`
- Test: `tests/test_fair.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_fair.py`:

```python
import json

import pytest

from sports_edge_scanner.core.fair import (
    FairProbabilityBook,
    fair_probability_for_outcome,
    load_fair_probability_book,
)
from sports_edge_scanner.models import Market, MarketOutcome


def make_market():
    return Market(
        id="market-1",
        title="Team A vs Team B",
        slug="team-a-team-b",
        active=True,
        closed=False,
        end_time=None,
        liquidity=5000.0,
        volume=10000.0,
        outcomes=[
            MarketOutcome(name="Team A", price=0.46, token_id="token-a"),
            MarketOutcome(name="Team B", price=0.54, token_id="token-b"),
        ],
        source="polymarket",
    )


def test_token_probability_overrides_market_outcome_probability():
    book = FairProbabilityBook(
        markets={"market-1": {"Team A": 0.55}},
        tokens={"token-a": 0.57},
    )

    assert fair_probability_for_outcome(make_market(), make_market().outcomes[0], book) == 0.57


def test_market_id_and_slug_lookup_are_supported():
    market = make_market()
    id_book = FairProbabilityBook(markets={"market-1": {"Team A": 0.55}}, tokens={})
    slug_book = FairProbabilityBook(markets={"team-a-team-b": {"Team B": 0.48}}, tokens={})

    assert fair_probability_for_outcome(market, market.outcomes[0], id_book) == 0.55
    assert fair_probability_for_outcome(market, market.outcomes[1], slug_book) == 0.48


def test_load_fair_probability_book_validates_probabilities(tmp_path):
    path = tmp_path / "fair.json"
    path.write_text(json.dumps({"tokens": {"token-a": 1.2}}), encoding="utf-8")

    with pytest.raises(ValueError, match="fair probability"):
        load_fair_probability_book(path)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_fair.py -q`

Expected: FAIL because `sports_edge_scanner.core.fair` does not exist.

- [ ] **Step 3: Implement fair probability book**

Create `sports_edge_scanner/core/fair.py`:

```python
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sports_edge_scanner.core.pricing import validate_probability
from sports_edge_scanner.models import Market, MarketOutcome


@dataclass(frozen=True)
class FairProbabilityBook:
    markets: dict[str, dict[str, float]] = field(default_factory=dict)
    tokens: dict[str, float] = field(default_factory=dict)


def _validate_probability(value: Any) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("fair probability must be numeric") from exc
    return validate_probability(probability, "fair probability")


def load_fair_probability_book(path: Path) -> FairProbabilityBook:
    if not path.exists():
        raise ValueError(f"fair probability file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets: dict[str, dict[str, float]] = {}
    for market_key, outcomes in dict(payload.get("markets") or {}).items():
        markets[str(market_key)] = {
            str(outcome_name): _validate_probability(probability)
            for outcome_name, probability in dict(outcomes).items()
        }
    tokens = {
        str(token_id): _validate_probability(probability)
        for token_id, probability in dict(payload.get("tokens") or {}).items()
    }
    return FairProbabilityBook(markets=markets, tokens=tokens)


def fair_probability_for_outcome(
    market: Market,
    outcome: MarketOutcome,
    book: FairProbabilityBook,
) -> float | None:
    if outcome.token_id and outcome.token_id in book.tokens:
        return book.tokens[outcome.token_id]
    for market_key in (market.id, market.slug):
        outcome_probabilities = book.markets.get(market_key, {})
        for outcome_key, probability in outcome_probabilities.items():
            if outcome_key.upper() == outcome.name.upper():
                return probability
    return None
```

- [ ] **Step 4: Run fair tests**

Run: `python -m pytest tests/test_fair.py -q`

Expected: PASS.

## Task 3: Public CLOB Orderbook Connector

**Files:**
- Create: `sports_edge_scanner/connectors/polymarket_clob.py`
- Test: `tests/test_polymarket_clob.py`

- [ ] **Step 1: Write failing connector tests**

Create `tests/test_polymarket_clob.py`:

```python
import json
from io import BytesIO

from sports_edge_scanner.connectors.polymarket_clob import (
    PolymarketCLOBClient,
    normalize_orderbook,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return BytesIO(self._payload)

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_normalize_orderbook_sorts_bid_and_ask_levels():
    payload = {
        "market": "market-1",
        "asset_id": "token-a",
        "bids": [{"price": "0.44", "size": "10"}, {"price": "0.45", "size": "5"}],
        "asks": [{"price": "0.48", "size": "5"}, {"price": "0.47", "size": "10"}],
        "timestamp": "2026-05-10T00:00:00+00:00",
    }

    book = normalize_orderbook(payload, fallback_token_id="token-a")

    assert book.market_id == "market-1"
    assert book.token_id == "token-a"
    assert [level.price for level in book.bids] == [0.45, 0.44]
    assert [level.price for level in book.asks] == [0.47, 0.48]


def test_fetch_orderbook_uses_token_id_parameter(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(
            {
                "market": "market-1",
                "asset_id": "token-a",
                "bids": [{"price": "0.44", "size": "10"}],
                "asks": [{"price": "0.47", "size": "10"}],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    book = PolymarketCLOBClient(base_url="https://clob.polymarket.com").fetch_orderbook(
        "token-a"
    )

    assert "token_id=token-a" in captured["url"]
    assert book.best_ask == 0.47
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_polymarket_clob.py -q`

Expected: FAIL because the connector does not exist.

- [ ] **Step 3: Implement CLOB connector**

Create `sports_edge_scanner/connectors/polymarket_clob.py`:

```python
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sports_edge_scanner.models import OrderBook, OrderBookLevel


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _levels(raw_levels: Any, reverse: bool) -> list[OrderBookLevel]:
    levels: list[OrderBookLevel] = []
    if not isinstance(raw_levels, list):
        return levels
    for raw_level in raw_levels:
        if not isinstance(raw_level, dict):
            continue
        price = _float_or_none(raw_level.get("price"))
        size = _float_or_none(raw_level.get("size"))
        if price is None or size is None or price <= 0.0 or price >= 1.0 or size <= 0.0:
            continue
        levels.append(OrderBookLevel(price=price, size=size))
    levels.sort(key=lambda level: level.price, reverse=reverse)
    return levels


def normalize_orderbook(payload: dict[str, Any], fallback_token_id: str) -> OrderBook:
    timestamp = str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat())
    return OrderBook(
        market_id=str(payload.get("market") or payload.get("market_id") or ""),
        token_id=str(payload.get("asset_id") or payload.get("token_id") or fallback_token_id),
        bids=_levels(payload.get("bids"), reverse=True),
        asks=_levels(payload.get("asks"), reverse=False),
        timestamp=timestamp,
        tick_size=_float_or_none(payload.get("tick_size")),
    )


class PolymarketCLOBClient:
    def __init__(self, base_url: str = "https://clob.polymarket.com") -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_orderbook(self, token_id: str) -> OrderBook:
        params = urllib.parse.urlencode({"token_id": token_id})
        url = f"{self.base_url}/book?{params}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "sports-edge-scanner/0.1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CLOB orderbook response must be an object")
        return normalize_orderbook(payload, fallback_token_id=token_id)
```

- [ ] **Step 4: Run connector tests**

Run: `python -m pytest tests/test_polymarket_clob.py -q`

Expected: PASS.

## Task 4: Shadow Signal Generation

**Files:**
- Create: `sports_edge_scanner/core/shadow_signals.py`
- Test: `tests/test_shadow_signals.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_shadow_signals.py`:

```python
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.shadow_signals import candidate_orders_for_market
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


def make_market():
    return Market(
        id="market-1",
        title="Team A vs Team B",
        slug="team-a-team-b",
        active=True,
        closed=False,
        end_time=None,
        liquidity=5000.0,
        volume=10000.0,
        outcomes=[
            MarketOutcome(name="Team A", price=0.46, token_id="token-a"),
            MarketOutcome(name="Team B", price=0.54, token_id="token-b"),
        ],
        source="polymarket",
    )


def test_candidate_generated_for_non_yes_no_outcome_with_edge():
    market = make_market()
    books = {
        "token-a": OrderBook(
            market_id="market-1",
            token_id="token-a",
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[OrderBookLevel(price=0.47, size=100.0)],
            timestamp="2026-05-10T00:00:00+00:00",
        )
    }
    fair = FairProbabilityBook(tokens={"token-a": 0.55})

    candidates = candidate_orders_for_market(
        market,
        fair,
        books,
        min_edge=0.03,
        default_notional=10.0,
    )

    assert len(candidates) == 1
    assert candidates[0].outcome_name == "Team A"
    assert candidates[0].limit_price == 0.47
    assert candidates[0].edge == 0.08


def test_no_candidate_without_token_id_or_book_or_edge():
    market = make_market()
    fair = FairProbabilityBook(markets={"market-1": {"Team A": 0.48}})

    assert candidate_orders_for_market(market, fair, {}, min_edge=0.03) == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_shadow_signals.py -q`

Expected: FAIL because `shadow_signals` does not exist.

- [ ] **Step 3: Implement candidate generation**

Create `sports_edge_scanner/core/shadow_signals.py`:

```python
from sports_edge_scanner.core.fair import FairProbabilityBook, fair_probability_for_outcome
from sports_edge_scanner.core.pricing import expected_value_per_unit
from sports_edge_scanner.models import CandidateOrder, Market, OrderBook


def candidate_orders_for_market(
    market: Market,
    fair_probabilities: FairProbabilityBook,
    orderbooks_by_token: dict[str, OrderBook],
    min_edge: float = 0.03,
    cost_buffer: float = 0.0,
    default_notional: float = 10.0,
) -> list[CandidateOrder]:
    if market.closed or not market.active:
        return []

    candidates: list[CandidateOrder] = []
    for outcome in market.outcomes:
        if not outcome.token_id:
            continue
        book = orderbooks_by_token.get(outcome.token_id)
        if book is None or book.best_ask is None:
            continue
        fair = fair_probability_for_outcome(market, outcome, fair_probabilities)
        if fair is None:
            continue
        edge = expected_value_per_unit(fair, book.best_ask, cost_buffer=cost_buffer)
        if edge < min_edge:
            continue
        candidates.append(
            CandidateOrder(
                market_id=market.id,
                market_slug=market.slug,
                outcome_name=outcome.name,
                token_id=outcome.token_id,
                side="BUY",
                limit_price=book.best_ask,
                requested_notional=default_notional,
                fair_probability=fair,
                edge=edge,
                reason="fair probability clears executable price",
            )
        )
    return candidates
```

- [ ] **Step 4: Run shadow signal tests**

Run: `python -m pytest tests/test_shadow_signals.py -q`

Expected: PASS.

## Task 5: Risk Controls

**Files:**
- Create: `sports_edge_scanner/core/risk.py`
- Test: `tests/test_risk.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_risk.py`:

```python
from sports_edge_scanner.core.risk import RiskConfig, evaluate_candidate_order
from sports_edge_scanner.models import CandidateOrder, OrderBook, OrderBookLevel


def make_candidate():
    return CandidateOrder(
        market_id="m1",
        market_slug="m1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=0.47,
        requested_notional=10.0,
        fair_probability=0.55,
        edge=0.08,
        reason="edge",
    )


def make_book():
    return OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.45, size=100.0)],
        asks=[OrderBookLevel(price=0.47, size=100.0)],
        timestamp="2026-05-10T00:00:00+00:00",
    )


def test_risk_allows_candidate_within_limits():
    decision = evaluate_candidate_order(
        make_candidate(),
        make_book(),
        RiskConfig(),
        market_exposure=0.0,
        total_exposure=0.0,
        daily_pnl=0.0,
    )

    assert decision.allowed is True
    assert decision.approved_notional == 10.0


def test_risk_reduces_to_order_and_market_limits():
    config = RiskConfig(max_order_notional=8.0, max_market_exposure=12.0)

    decision = evaluate_candidate_order(
        make_candidate(),
        make_book(),
        config,
        market_exposure=6.0,
        total_exposure=0.0,
        daily_pnl=0.0,
    )

    assert decision.allowed is True
    assert decision.approved_notional == 6.0
    assert "reduced for max_market_exposure" in decision.reasons


def test_risk_rejects_wide_spread_and_daily_loss():
    config = RiskConfig(max_spread=0.01, daily_loss_limit=5.0)
    book = OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.40, size=100.0)],
        asks=[OrderBookLevel(price=0.47, size=100.0)],
        timestamp="2026-05-10T00:00:00+00:00",
    )

    decision = evaluate_candidate_order(
        make_candidate(),
        book,
        config,
        market_exposure=0.0,
        total_exposure=0.0,
        daily_pnl=-5.0,
    )

    assert decision.allowed is False
    assert "wide spread" in decision.reasons
    assert "daily loss limit reached" in decision.reasons
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_risk.py -q`

Expected: FAIL because `risk` does not exist.

- [ ] **Step 3: Implement risk config and evaluator**

Create `sports_edge_scanner/core/risk.py`:

```python
from dataclasses import dataclass

from sports_edge_scanner.models import CandidateOrder, OrderBook, RiskDecision


@dataclass(frozen=True)
class RiskConfig:
    max_order_notional: float = 10.0
    max_market_exposure: float = 25.0
    max_total_exposure: float = 100.0
    min_liquidity: float = 1000.0
    max_spread: float = 0.08
    max_slippage: float = 0.02
    min_edge: float = 0.03
    daily_loss_limit: float = 25.0
    stale_book_seconds: int = 30


def evaluate_candidate_order(
    candidate: CandidateOrder,
    orderbook: OrderBook,
    config: RiskConfig,
    market_exposure: float,
    total_exposure: float,
    daily_pnl: float,
) -> RiskDecision:
    reasons: list[str] = []
    approved = candidate.requested_notional

    if daily_pnl <= -abs(config.daily_loss_limit):
        reasons.append("daily loss limit reached")
    if candidate.edge < config.min_edge:
        reasons.append("edge below minimum")
    if orderbook.spread is None:
        reasons.append("missing spread")
    elif orderbook.spread > config.max_spread:
        reasons.append("wide spread")

    if approved > config.max_order_notional:
        approved = config.max_order_notional
        reasons.append("reduced for max_order_notional")

    remaining_market = config.max_market_exposure - market_exposure
    if remaining_market < approved:
        approved = max(0.0, remaining_market)
        reasons.append("reduced for max_market_exposure")

    remaining_total = config.max_total_exposure - total_exposure
    if remaining_total < approved:
        approved = max(0.0, remaining_total)
        reasons.append("reduced for max_total_exposure")

    if approved <= 0.0:
        reasons.append("no remaining exposure capacity")

    hard_rejections = {
        "daily loss limit reached",
        "edge below minimum",
        "missing spread",
        "wide spread",
        "no remaining exposure capacity",
    }
    allowed = approved > 0.0 and not any(reason in hard_rejections for reason in reasons)
    if allowed and not reasons:
        reasons.append("allowed")

    return RiskDecision(
        allowed=allowed,
        reasons=reasons,
        requested_notional=candidate.requested_notional,
        approved_notional=approved if allowed else 0.0,
    )
```

- [ ] **Step 4: Run risk tests**

Run: `python -m pytest tests/test_risk.py -q`

Expected: PASS.

## Task 6: Shadow Execution

**Files:**
- Create: `sports_edge_scanner/core/shadow_execution.py`
- Test: `tests/test_shadow_execution.py`

- [ ] **Step 1: Write failing fill simulation tests**

Create `tests/test_shadow_execution.py`:

```python
import pytest

from sports_edge_scanner.core.shadow_execution import simulate_buy_limit_fill
from sports_edge_scanner.models import OrderBook, OrderBookLevel, ShadowOrder


def make_order(notional=10.0, limit_price=0.50):
    return ShadowOrder(
        order_id="shadow-1",
        market_id="m1",
        outcome_name="Team A",
        token_id="token-a",
        side="BUY",
        limit_price=limit_price,
        notional=notional,
        source_signal_id="signal-1",
    )


def make_book():
    return OrderBook(
        market_id="m1",
        token_id="token-a",
        bids=[OrderBookLevel(price=0.44, size=100.0)],
        asks=[
            OrderBookLevel(price=0.47, size=10.0),
            OrderBookLevel(price=0.49, size=10.0),
            OrderBookLevel(price=0.52, size=10.0),
        ],
        timestamp="2026-05-10T00:00:00+00:00",
    )


def test_full_fill_walks_asks_up_to_limit():
    fill = simulate_buy_limit_fill(make_order(notional=8.0, limit_price=0.50), make_book())

    assert fill.status == "full"
    assert fill.filled_notional == pytest.approx(8.0)
    assert fill.unfilled_notional == pytest.approx(0.0)
    assert fill.average_price == pytest.approx(0.47)


def test_partial_fill_stops_at_limit_price():
    fill = simulate_buy_limit_fill(make_order(notional=12.0, limit_price=0.48), make_book())

    assert fill.status == "partial"
    assert fill.filled_notional == pytest.approx(4.7)
    assert fill.unfilled_notional == pytest.approx(7.3)


def test_unfilled_when_no_ask_is_at_or_below_limit():
    fill = simulate_buy_limit_fill(make_order(notional=10.0, limit_price=0.46), make_book())

    assert fill.status == "unfilled"
    assert fill.average_price is None
    assert fill.filled_notional == 0.0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_shadow_execution.py -q`

Expected: FAIL because `shadow_execution` does not exist.

- [ ] **Step 3: Implement buy limit fill simulation**

Create `sports_edge_scanner/core/shadow_execution.py`:

```python
from sports_edge_scanner.models import OrderBook, ShadowFill, ShadowOrder


def simulate_buy_limit_fill(order: ShadowOrder, orderbook: OrderBook) -> ShadowFill:
    remaining_notional = order.notional
    filled_notional = 0.0
    filled_contracts = 0.0
    consumed: list[dict[str, float]] = []
    best_ask = orderbook.best_ask

    for level in sorted(orderbook.asks, key=lambda item: item.price):
        if level.price > order.limit_price or remaining_notional <= 0.0:
            break
        level_notional = level.price * level.size
        take_notional = min(remaining_notional, level_notional)
        take_contracts = take_notional / level.price
        filled_notional += take_notional
        filled_contracts += take_contracts
        remaining_notional -= take_notional
        consumed.append(
            {
                "price": level.price,
                "notional": take_notional,
                "contracts": take_contracts,
            }
        )

    if filled_notional == 0.0:
        status = "unfilled"
        average_price = None
    elif remaining_notional > 1e-9:
        status = "partial"
        average_price = filled_notional / filled_contracts
    else:
        status = "full"
        average_price = filled_notional / filled_contracts

    slippage = 0.0
    if average_price is not None and best_ask is not None:
        slippage = average_price - best_ask

    return ShadowFill(
        order_id=order.order_id,
        status=status,
        requested_notional=order.notional,
        filled_notional=filled_notional,
        filled_contracts=filled_contracts,
        average_price=average_price,
        unfilled_notional=max(0.0, remaining_notional),
        slippage=slippage,
        consumed_levels=consumed,
    )
```

- [ ] **Step 4: Run execution tests**

Run: `python -m pytest tests/test_shadow_execution.py -q`

Expected: PASS.

## Task 7: Shadow Event Log

**Files:**
- Create: `sports_edge_scanner/core/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write failing event tests**

Create `tests/test_events.py`:

```python
from sports_edge_scanner.core.events import append_event, make_event, read_events


def test_make_event_adds_schema_run_and_timestamp():
    event = make_event(
        "signal",
        run_id="run-1",
        payload={"market_id": "m1", "status": "candidate"},
        timestamp="2026-05-10T00:00:00+00:00",
    )

    assert event["schema_version"] == 1
    assert event["event_type"] == "signal"
    assert event["run_id"] == "run-1"
    assert event["market_id"] == "m1"


def test_append_and_read_events_round_trip(tmp_path):
    path = tmp_path / "shadow_events.jsonl"
    event = make_event(
        "shadow_fill",
        run_id="run-1",
        payload={"order_id": "shadow-1"},
        timestamp="2026-05-10T00:00:00+00:00",
    )

    append_event(path, event)

    assert read_events(path) == [event]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_events.py -q`

Expected: FAIL because `events` does not exist.

- [ ] **Step 3: Implement event helpers**

Create `sports_edge_scanner/core/events.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def make_event(
    event_type: str,
    run_id: str,
    payload: dict[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        **payload,
    }
    return event


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                events.append(json.loads(stripped))
    return events
```

- [ ] **Step 4: Run event tests**

Run: `python -m pytest tests/test_events.py -q`

Expected: PASS.

## Task 8: Shadow Reports

**Files:**
- Create: `sports_edge_scanner/core/shadow_reports.py`
- Test: `tests/test_shadow_reports.py`

- [ ] **Step 1: Write failing report tests**

Create `tests/test_shadow_reports.py`:

```python
import pytest

from sports_edge_scanner.core.shadow_reports import build_shadow_report


def test_shadow_report_counts_orders_fills_and_rejections():
    events = [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {"event_type": "risk_decision", "allowed": False, "reasons": ["wide spread"]},
        {
            "event_type": "risk_decision",
            "allowed": True,
            "reasons": ["allowed"],
            "approved_notional": 10.0,
        },
        {"event_type": "shadow_order", "notional": 10.0, "market_id": "m1"},
        {
            "event_type": "shadow_fill",
            "status": "full",
            "filled_notional": 10.0,
            "slippage": 0.01,
        },
        {
            "event_type": "shadow_fill",
            "status": "partial",
            "filled_notional": 5.0,
            "slippage": 0.02,
        },
    ]

    report = build_shadow_report(events)

    assert report["candidate_count"] == 1
    assert report["accepted_order_count"] == 1
    assert report["rejected_order_count"] == 1
    assert report["rejections_by_reason"] == {"wide spread": 1}
    assert report["fill_status_counts"] == {"full": 1, "partial": 1}
    assert report["simulated_notional_filled"] == 15.0
    assert report["average_slippage"] == pytest.approx(0.015)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: FAIL because `shadow_reports` does not exist.

- [ ] **Step 3: Implement shadow report aggregation**

Create `sports_edge_scanner/core/shadow_reports.py`:

```python
from typing import Any


def build_shadow_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_count = sum(
        1
        for event in events
        if event.get("event_type") == "signal" and event.get("status") == "candidate"
    )
    accepted_order_count = 0
    rejected_order_count = 0
    rejections_by_reason: dict[str, int] = {}
    fill_status_counts: dict[str, int] = {}
    filled_notional = 0.0
    slippages: list[float] = []

    for event in events:
        event_type = event.get("event_type")
        if event_type == "risk_decision":
            if event.get("allowed"):
                accepted_order_count += 1
            else:
                rejected_order_count += 1
                for reason in event.get("reasons") or []:
                    rejections_by_reason[str(reason)] = rejections_by_reason.get(str(reason), 0) + 1
        elif event_type == "shadow_fill":
            status = str(event.get("status") or "unknown")
            fill_status_counts[status] = fill_status_counts.get(status, 0) + 1
            filled_notional += float(event.get("filled_notional") or 0.0)
            slippages.append(float(event.get("slippage") or 0.0))

    return {
        "candidate_count": candidate_count,
        "accepted_order_count": accepted_order_count,
        "rejected_order_count": rejected_order_count,
        "rejections_by_reason": rejections_by_reason,
        "fill_status_counts": fill_status_counts,
        "simulated_notional_filled": filled_notional,
        "average_slippage": sum(slippages) / len(slippages) if slippages else 0.0,
    }
```

- [ ] **Step 4: Run shadow report tests**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: PASS.

## Task 9: CLI Shadow Commands With Mockable Pipeline

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Test: `tests/test_cli_shadow.py`

- [ ] **Step 1: Write failing CLI parser and pipeline tests**

Create `tests/test_cli_shadow.py`:

```python
import json

from sports_edge_scanner.cli import build_parser, run_shadow_scan
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


class FakeMarketClient:
    def fetch_markets(self, limit):
        return [
            Market(
                id="m1",
                title="Team A vs Team B",
                slug="team-a-team-b",
                active=True,
                closed=False,
                end_time=None,
                liquidity=5000.0,
                volume=10000.0,
                outcomes=[
                    MarketOutcome(name="Team A", price=0.46, token_id="token-a"),
                    MarketOutcome(name="Team B", price=0.54, token_id="token-b"),
                ],
                source="polymarket",
            )
        ]


class FakeBookClient:
    def fetch_orderbook(self, token_id):
        return OrderBook(
            market_id="m1",
            token_id=token_id,
            bids=[OrderBookLevel(price=0.45, size=100.0)],
            asks=[OrderBookLevel(price=0.47, size=100.0)],
            timestamp="2026-05-10T00:00:00+00:00",
        )


def test_parser_supports_shadow_scan_and_report():
    parser = build_parser()

    scan_args = parser.parse_args(["shadow", "scan", "--limit", "5"])
    report_args = parser.parse_args(["shadow", "report", "--events", "shadow.jsonl"])

    assert scan_args.command == "shadow"
    assert scan_args.shadow_command == "scan"
    assert report_args.shadow_command == "report"


def test_run_shadow_scan_writes_signal_risk_order_and_fill_events(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"

    summary = run_shadow_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=FairProbabilityBook(tokens={"token-a": 0.55}),
        risk_config=RiskConfig(),
        limit=5,
        events_path=events_path,
        run_id="run-1",
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    event_types = [event["event_type"] for event in events]

    assert summary["candidate_count"] == 1
    assert "signal" in event_types
    assert "risk_decision" in event_types
    assert "shadow_order" in event_types
    assert "shadow_fill" in event_types
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: FAIL because CLI does not support shadow commands and `run_shadow_scan` does not exist.

- [ ] **Step 3: Add CLI imports and run_shadow_scan helper**

Modify `sports_edge_scanner/cli.py` to import:

```python
from uuid import uuid4

from sports_edge_scanner.connectors.polymarket_clob import PolymarketCLOBClient
from sports_edge_scanner.core.events import append_event, make_event, read_events
from sports_edge_scanner.core.fair import FairProbabilityBook, load_fair_probability_book
from sports_edge_scanner.core.risk import RiskConfig, evaluate_candidate_order
from sports_edge_scanner.core.shadow_execution import simulate_buy_limit_fill
from sports_edge_scanner.core.shadow_reports import build_shadow_report
from sports_edge_scanner.core.shadow_signals import candidate_orders_for_market
from sports_edge_scanner.models import CandidateOrder, OrderBook, ShadowOrder
```

Add these helpers near the existing command helpers:

```python
def _order_id(run_id: str, index: int) -> str:
    return f"{run_id}-shadow-{index}"


def run_shadow_scan(
    market_client,
    book_client,
    fair_book: FairProbabilityBook,
    risk_config: RiskConfig,
    limit: int,
    events_path: Path,
    run_id: str,
) -> dict[str, object]:
    markets = market_client.fetch_markets(limit=limit)
    candidate_count = 0
    accepted_count = 0
    rejected_count = 0
    order_index = 0

    for market in markets:
        books: dict[str, OrderBook] = {}
        for outcome in market.outcomes:
            if outcome.token_id:
                try:
                    books[outcome.token_id] = book_client.fetch_orderbook(outcome.token_id)
                except Exception as exc:
                    append_event(
                        events_path,
                        make_event(
                            "orderbook_error",
                            run_id,
                            {
                                "market_id": market.id,
                                "token_id": outcome.token_id,
                                "error": str(exc),
                            },
                        ),
                    )

        candidates = candidate_orders_for_market(
            market,
            fair_book,
            books,
            min_edge=risk_config.min_edge,
            default_notional=risk_config.max_order_notional,
        )
        for candidate in candidates:
            candidate_count += 1
            append_event(
                events_path,
                make_event(
                    "signal",
                    run_id,
                    {"status": "candidate", **candidate.to_dict()},
                ),
            )
            book = books[candidate.token_id]
            decision = evaluate_candidate_order(
                candidate,
                book,
                risk_config,
                market_exposure=0.0,
                total_exposure=0.0,
                daily_pnl=0.0,
            )
            append_event(
                events_path,
                make_event(
                    "risk_decision",
                    run_id,
                    {
                        "market_id": candidate.market_id,
                        "token_id": candidate.token_id,
                        **decision.to_dict(),
                    },
                ),
            )
            if not decision.allowed:
                rejected_count += 1
                continue

            accepted_count += 1
            order_index += 1
            order = ShadowOrder(
                order_id=_order_id(run_id, order_index),
                market_id=candidate.market_id,
                outcome_name=candidate.outcome_name,
                token_id=candidate.token_id,
                side="BUY",
                limit_price=candidate.limit_price,
                notional=decision.approved_notional,
                source_signal_id=f"{run_id}-signal-{candidate_count}",
            )
            append_event(events_path, make_event("shadow_order", run_id, order.to_dict()))
            fill = simulate_buy_limit_fill(order, book)
            append_event(
                events_path,
                make_event(
                    "shadow_fill",
                    run_id,
                    {
                        "market_id": candidate.market_id,
                        "token_id": candidate.token_id,
                        **fill.to_dict(),
                    },
                ),
            )

    return {
        "markets": len(markets),
        "candidate_count": candidate_count,
        "accepted_order_count": accepted_count,
        "rejected_order_count": rejected_count,
        "events_path": str(events_path),
    }
```

- [ ] **Step 4: Add shadow argparse commands**

Inside `build_parser()`, add after existing subparser declarations:

```python
    shadow = subparsers.add_parser("shadow", help="Run shadow trading simulations.")
    shadow_subparsers = shadow.add_subparsers(dest="shadow_command", required=True)

    shadow_scan = shadow_subparsers.add_parser(
        "scan",
        help="Scan markets and simulate risk-checked shadow orders.",
    )
    shadow_scan.add_argument("--limit", type=int, default=20)
    shadow_scan.add_argument("--fair", default="", help="Fair probability JSON file.")
    shadow_scan.add_argument("--config", default="", help="Shadow risk config JSON file.")
    shadow_scan.add_argument("--events", default="shadow_events.jsonl")
    shadow_scan.add_argument("--json", action="store_true")
    shadow_scan.set_defaults(func=_shadow_scan)

    shadow_report = shadow_subparsers.add_parser(
        "report",
        help="Summarize shadow event logs.",
    )
    shadow_report.add_argument("--events", default="shadow_events.jsonl")
    shadow_report.add_argument("--json", action="store_true")
    shadow_report.set_defaults(func=_shadow_report)
```

Add command functions:

```python
def _load_risk_config(path_value: str) -> RiskConfig:
    if not path_value:
        return RiskConfig()
    payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
    return RiskConfig(**payload)


def _shadow_scan(args: argparse.Namespace) -> int:
    try:
        fair_book = (
            load_fair_probability_book(Path(args.fair))
            if args.fair
            else FairProbabilityBook()
        )
        summary = run_shadow_scan(
            market_client=PolymarketClient(),
            book_client=PolymarketCLOBClient(),
            fair_book=fair_book,
            risk_config=_load_risk_config(args.config),
            limit=args.limit,
            events_path=Path(args.events),
            run_id=str(uuid4()),
        )
    except Exception as exc:
        print(f"shadow scan failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Markets: {summary['markets']}")
        print(f"Candidates: {summary['candidate_count']}")
        print(f"Accepted shadow orders: {summary['accepted_order_count']}")
        print(f"Rejected shadow orders: {summary['rejected_order_count']}")
        print(f"Events: {summary['events_path']}")
    return 0


def _shadow_report(args: argparse.Namespace) -> int:
    report = build_shadow_report(read_events(Path(args.events)))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Candidates: {report['candidate_count']}")
        print(f"Accepted shadow orders: {report['accepted_order_count']}")
        print(f"Rejected shadow orders: {report['rejected_order_count']}")
        print(f"Simulated notional filled: ${report['simulated_notional_filled']:,.2f}")
        print(f"Average slippage: {report['average_slippage']:.4f}")
    return 0
```

- [ ] **Step 5: Run CLI shadow tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

## Task 10: README And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document shadow mode**

Add a `Shadow Trading Simulation` section to `README.md`:

```markdown
## Shadow Trading Simulation

Shadow mode rehearses live-trading decisions without sending real orders, signing payloads, storing private keys, or controlling funds.

Example fair probability file:

```json
{
  "markets": {
    "example-market-slug": {
      "Team A": 0.57
    }
  },
  "tokens": {
    "example-token-id": 0.57
  }
}
```

Run a bounded shadow scan:

```bash
python -m sports_edge_scanner shadow scan --limit 20 --fair fair_probabilities.json --events shadow_events.jsonl
python -m sports_edge_scanner shadow report --events shadow_events.jsonl
```

Every candidate is either rejected with explicit risk reasons or converted into a simulated limit order and fill record. Shadow results are not live fills and should be treated as research evidence only.
```

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_shadow_models.py tests/test_fair.py tests/test_polymarket_clob.py tests/test_shadow_signals.py tests/test_risk.py tests/test_shadow_execution.py tests/test_events.py tests/test_shadow_reports.py tests/test_cli_shadow.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run CLI smoke commands without network**

Run:

```bash
python -m sports_edge_scanner shadow report --events missing-shadow-events.jsonl --json
python -m sports_edge_scanner --help
```

Expected: report command exits 0 with zero counts; help includes `shadow`.

- [ ] **Step 5: Review diff**

Run: `git diff --stat`

Expected: only source, tests, README, and this plan are changed.

