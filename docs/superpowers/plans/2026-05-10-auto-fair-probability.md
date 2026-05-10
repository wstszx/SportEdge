# Auto Fair Probability Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let shadow simulation run without operator-edited fair probability files by generating conservative, auditable automatic probability estimates from public market/orderbook data.

**Architecture:** Add a focused `sports_edge_scanner.core.auto_fair` module that produces `FairProbabilityEstimate` objects and converts usable estimates into `FairProbabilityBook`. Integrate it into `shadow_pipeline` and CLI only when `--fair` is omitted, keeping manual fair files as an explicit override.

**Tech Stack:** Python 3.10+, dataclasses, existing market/orderbook models, existing JSONL event helpers, pytest.

---

## File Structure

- Create `sports_edge_scanner/core/auto_fair.py`: auto fair config, estimate dataclass, market estimator, and book builder.
- Modify `sports_edge_scanner/core/shadow_pipeline.py`: optionally estimate fair probabilities per market and append `model_estimate` events.
- Modify `sports_edge_scanner/core/shadow_state.py`: count model estimate events and rejection reasons.
- Modify `sports_edge_scanner/cli.py`: allow `shadow scan` without `--fair` and add `--auto-fair-min-confidence`.
- Modify `README.md`: document no-manual-edit shadow workflow.
- Add tests in `tests/test_auto_fair.py`, `tests/test_cli_shadow.py`, and `tests/test_shadow_reports.py`.

## Task 1: Auto Fair Estimator

**Files:**
- Create: `sports_edge_scanner/core/auto_fair.py`
- Create: `tests/test_auto_fair.py`

- [ ] **Step 1: Write failing estimator tests**

Create `tests/test_auto_fair.py`:

```python
import pytest

from sports_edge_scanner.core.auto_fair import (
    AutoFairConfig,
    build_auto_fair_probability_book,
    estimate_fair_probabilities_for_market,
)
from sports_edge_scanner.models import Market, MarketOutcome, OrderBook, OrderBookLevel


def market(**overrides):
    values = {
        "id": "m1",
        "title": "Team A vs Team B",
        "slug": "team-a-team-b",
        "active": True,
        "closed": False,
        "end_time": None,
        "liquidity": 5000.0,
        "volume": 10000.0,
        "outcomes": [
            MarketOutcome(name="Team A", price=0.51, token_id="token-a"),
            MarketOutcome(name="Team B", price=0.49, token_id="token-b"),
        ],
        "source": "polymarket",
    }
    values.update(overrides)
    return Market(**values)


def book(token_id="token-a", bid=0.49, ask=0.51, size=100.0):
    return OrderBook(
        market_id="m1",
        token_id=token_id,
        bids=[OrderBookLevel(price=bid, size=size)],
        asks=[OrderBookLevel(price=ask, size=size)],
        timestamp="2026-05-10T00:00:00+00:00",
    )


def test_estimate_uses_orderbook_midpoint_when_available():
    estimates = estimate_fair_probabilities_for_market(
        market(),
        {"token-a": book()},
        AutoFairConfig(min_confidence=0.75),
    )

    estimate = estimates[0]
    assert estimate.probability == pytest.approx(0.50)
    assert estimate.confidence >= 0.75
    assert estimate.source == "orderbook_midpoint"
    assert estimate.usable is True


def test_estimate_falls_back_to_display_price_with_low_confidence():
    estimates = estimate_fair_probabilities_for_market(
        market(),
        {},
        AutoFairConfig(min_confidence=0.75),
    )

    estimate = estimates[0]
    assert estimate.probability == 0.51
    assert estimate.confidence <= 0.55
    assert estimate.usable is False
    assert "display price only" in estimate.reasons


def test_closed_market_estimate_is_unusable():
    estimates = estimate_fair_probabilities_for_market(
        market(active=False, closed=True),
        {"token-a": book()},
        AutoFairConfig(min_confidence=0.75),
    )

    assert estimates[0].usable is False
    assert "market closed or inactive" in estimates[0].reasons


def test_wide_spread_and_low_liquidity_reduce_confidence():
    estimates = estimate_fair_probabilities_for_market(
        market(liquidity=100.0),
        {"token-a": book(bid=0.40, ask=0.60, size=1.0)},
        AutoFairConfig(min_confidence=0.75, min_liquidity=1000.0, max_spread=0.08),
    )

    estimate = estimates[0]
    assert estimate.usable is False
    assert "wide spread" in estimate.reasons
    assert "low liquidity" in estimate.reasons
    assert "thin top of book" in estimate.reasons


def test_auto_fair_book_includes_only_usable_estimates():
    fair_book, estimates = build_auto_fair_probability_book(
        [market()],
        {"m1": {"token-a": book(), "token-b": book(token_id="token-b", bid=0.48, ask=0.50)}},
        AutoFairConfig(min_confidence=0.75),
    )

    assert fair_book.tokens["token-a"] == pytest.approx(0.50)
    assert fair_book.tokens["token-b"] == pytest.approx(0.49)
    assert len(estimates) == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_auto_fair.py -q`

Expected: FAIL because `sports_edge_scanner.core.auto_fair` does not exist.

- [ ] **Step 3: Implement auto fair module**

Create `sports_edge_scanner/core/auto_fair.py`:

```python
from dataclasses import asdict, dataclass
from typing import Any

from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.models import Market, OrderBook


@dataclass(frozen=True)
class AutoFairConfig:
    min_confidence: float = 0.75
    min_liquidity: float = 1000.0
    max_spread: float = 0.08
    min_top_book_size: float = 10.0
    orderbook_weight: float = 1.0
    display_price_weight: float = 0.5


@dataclass(frozen=True)
class FairProbabilityEstimate:
    market_id: str
    market_slug: str
    outcome_name: str
    token_id: str
    probability: float | None
    confidence: float
    source: str
    reasons: list[str]
    usable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _top_book_size(orderbook: OrderBook) -> float:
    bid_size = max((level.size for level in orderbook.bids), default=0.0)
    ask_size = max((level.size for level in orderbook.asks), default=0.0)
    return min(bid_size, ask_size)


def _estimate_for_orderbook(orderbook: OrderBook) -> float | None:
    if orderbook.best_bid is None or orderbook.best_ask is None:
        return None
    return (orderbook.best_bid + orderbook.best_ask) / 2


def estimate_fair_probabilities_for_market(
    market: Market,
    orderbooks_by_token: dict[str, OrderBook],
    config: AutoFairConfig,
) -> list[FairProbabilityEstimate]:
    estimates: list[FairProbabilityEstimate] = []
    for outcome in market.outcomes:
        if not outcome.token_id:
            continue
        reasons: list[str] = []
        confidence = 1.0
        source = "orderbook_midpoint"
        probability = None
        orderbook = orderbooks_by_token.get(outcome.token_id)

        if market.closed or not market.active:
            confidence = 0.0
            reasons.append("market closed or inactive")

        if orderbook is not None:
            probability = _estimate_for_orderbook(orderbook)
            if probability is None:
                reasons.append("missing orderbook price")
                confidence -= 0.5
            elif orderbook.spread is not None and orderbook.spread > config.max_spread:
                reasons.append("wide spread")
                confidence -= 0.35
            if _top_book_size(orderbook) < config.min_top_book_size:
                reasons.append("thin top of book")
                confidence -= 0.25
        elif outcome.price is not None:
            probability = outcome.price
            source = "display_price"
            confidence = min(confidence, 0.55)
            reasons.append("display price only")
        else:
            source = "missing"
            confidence = 0.0
            reasons.append("missing price")

        if market.liquidity < config.min_liquidity:
            reasons.append("low liquidity")
            confidence -= 0.25

        confidence = max(0.0, min(1.0, confidence))
        usable = probability is not None and confidence >= config.min_confidence
        if usable and not reasons:
            reasons.append("usable automatic estimate")

        estimates.append(
            FairProbabilityEstimate(
                market_id=market.id,
                market_slug=market.slug,
                outcome_name=outcome.name,
                token_id=outcome.token_id,
                probability=probability,
                confidence=confidence,
                source=source,
                reasons=reasons,
                usable=usable,
            )
        )
    return estimates


def build_auto_fair_probability_book(
    markets: list[Market],
    orderbooks_by_market: dict[str, dict[str, OrderBook]],
    config: AutoFairConfig,
) -> tuple[FairProbabilityBook, list[FairProbabilityEstimate]]:
    estimates: list[FairProbabilityEstimate] = []
    tokens: dict[str, float] = {}
    for market in markets:
        market_estimates = estimate_fair_probabilities_for_market(
            market,
            orderbooks_by_market.get(market.id, {}),
            config,
        )
        estimates.extend(market_estimates)
        for estimate in market_estimates:
            if estimate.usable and estimate.probability is not None:
                tokens[estimate.token_id] = estimate.probability
    return FairProbabilityBook(tokens=tokens), estimates
```

- [ ] **Step 4: Run auto fair tests**

Run: `python -m pytest tests/test_auto_fair.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/auto_fair.py tests/test_auto_fair.py
git commit -m "feat: add auto fair estimator"
```

## Task 2: Shadow Pipeline Auto Fair Integration

**Files:**
- Modify: `sports_edge_scanner/core/shadow_pipeline.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Add failing shadow integration tests**

Append to `tests/test_cli_shadow.py`:

```python
from sports_edge_scanner.core.auto_fair import AutoFairConfig


def test_run_shadow_scan_without_manual_fair_emits_model_estimates(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"

    summary = run_shadow_scan(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        fair_book=None,
        risk_config=RiskConfig(min_edge=0.03),
        limit=5,
        events_path=events_path,
        run_id="run-1",
        auto_fair_config=AutoFairConfig(min_confidence=0.75),
        now=datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc),
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    estimate_events = [event for event in events if event["event_type"] == "model_estimate"]

    assert summary["model_estimate_count"] == 2
    assert len(estimate_events) == 2
    assert summary["candidate_count"] == 0
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_cli_shadow.py::test_run_shadow_scan_without_manual_fair_emits_model_estimates -q
```

Expected: FAIL because `run_shadow_scan` does not accept `fair_book=None` or `auto_fair_config`.

- [ ] **Step 3: Update shadow pipeline**

Modify imports in `sports_edge_scanner/core/shadow_pipeline.py`:

```python
from sports_edge_scanner.core.auto_fair import (
    AutoFairConfig,
    estimate_fair_probabilities_for_market,
)
```

Change signature:

```python
def run_shadow_scan(
    market_client: Any,
    book_client: Any,
    fair_book: FairProbabilityBook | None,
    risk_config: RiskConfig,
    limit: int,
    events_path: Path,
    run_id: str,
    now: datetime | None = None,
    auto_fair_config: AutoFairConfig | None = None,
) -> dict[str, object]:
```

Inside each market, after orderbook fetch and before `candidate_orders_for_market`, add:

```python
        market_fair_book = fair_book
        model_estimate_count = 0
```

But counters must live outside the market loop:

```python
    model_estimate_count = 0
    usable_model_estimate_count = 0
```

Inside market loop:

```python
        market_fair_book = fair_book
        if market_fair_book is None:
            market_fair_book = FairProbabilityBook()
            estimates = estimate_fair_probabilities_for_market(
                market,
                books,
                auto_fair_config or AutoFairConfig(),
            )
            for estimate in estimates:
                model_estimate_count += 1
                if estimate.usable:
                    usable_model_estimate_count += 1
                    if estimate.probability is not None:
                        market_fair_book.tokens[estimate.token_id] = estimate.probability
                append_event(
                    events_path,
                    make_event("model_estimate", run_id, estimate.to_dict()),
                )
```

Use `market_fair_book` in candidate generation:

```python
        candidates = candidate_orders_for_market(
            market,
            market_fair_book,
            books,
            min_edge=risk_config.min_edge,
            default_notional=risk_config.max_order_notional,
        )
```

Add summary fields:

```python
        "model_estimate_count": model_estimate_count,
        "usable_model_estimate_count": usable_model_estimate_count,
```

- [ ] **Step 4: Run shadow CLI tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/shadow_pipeline.py tests/test_cli_shadow.py
git commit -m "feat: integrate auto fair into shadow scan"
```

## Task 3: Shadow Report Model Estimate Counts

**Files:**
- Modify: `sports_edge_scanner/core/shadow_state.py`
- Modify: `tests/test_shadow_reports.py`

- [ ] **Step 1: Add failing report test**

Append to `tests/test_shadow_reports.py`:

```python
def test_shadow_report_counts_model_estimates_and_reasons():
    report = build_shadow_report(
        [
            {
                "event_type": "model_estimate",
                "usable": False,
                "reasons": ["display price only", "low liquidity"],
            },
            {
                "event_type": "model_estimate",
                "usable": True,
                "reasons": ["usable automatic estimate"],
            },
        ]
    )

    assert report["model_estimate_count"] == 2
    assert report["usable_model_estimate_count"] == 1
    assert report["unusable_model_estimate_count"] == 1
    assert report["model_rejections_by_reason"]["display price only"] == 1
    assert report["model_rejections_by_reason"]["low liquidity"] == 1
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_shadow_reports.py::test_shadow_report_counts_model_estimates_and_reasons -q
```

Expected: FAIL because report fields do not exist.

- [ ] **Step 3: Update shadow state**

Modify `sports_edge_scanner/core/shadow_state.py`:

Add counters:

```python
    model_estimate_count = 0
    usable_model_estimate_count = 0
    model_rejections_by_reason: dict[str, int] = {}
```

In event loop:

```python
        elif event_type == "model_estimate":
            model_estimate_count += 1
            if event.get("usable"):
                usable_model_estimate_count += 1
            else:
                for reason in event.get("reasons") or []:
                    reason_text = str(reason)
                    model_rejections_by_reason[reason_text] = (
                        model_rejections_by_reason.get(reason_text, 0) + 1
                    )
```

Add return fields:

```python
        "model_estimate_count": model_estimate_count,
        "usable_model_estimate_count": usable_model_estimate_count,
        "unusable_model_estimate_count": model_estimate_count - usable_model_estimate_count,
        "model_rejections_by_reason": model_rejections_by_reason,
```

- [ ] **Step 4: Run shadow report tests**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/shadow_state.py tests/test_shadow_reports.py
git commit -m "feat: report auto fair estimates"
```

## Task 4: CLI Defaults And Auto Fair Option

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Add failing CLI parser test**

Append to `tests/test_cli_shadow.py`:

```python
def test_parser_supports_shadow_scan_without_fair_and_auto_confidence():
    parser = build_parser()

    args = parser.parse_args(
        ["shadow", "scan", "--limit", "5", "--auto-fair-min-confidence", "0.8"]
    )

    assert args.fair == ""
    assert args.auto_fair_min_confidence == 0.8
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_cli_shadow.py::test_parser_supports_shadow_scan_without_fair_and_auto_confidence -q
```

Expected: FAIL because parser option does not exist.

- [ ] **Step 3: Update CLI**

Modify imports:

```python
from sports_edge_scanner.core.auto_fair import AutoFairConfig
```

In `_shadow_scan`, pass:

```python
        summary = run_shadow_scan(
            ...
            fair_book=fair_book,
            ...
            auto_fair_config=AutoFairConfig(
                min_confidence=args.auto_fair_min_confidence,
            ),
        )
```

Keep existing:

```python
        fair_book = (
            load_fair_probability_book(Path(args.fair))
            if args.fair
            else None
        )
```

Add parser argument:

```python
    shadow_scan.add_argument("--auto-fair-min-confidence", type=float, default=0.75)
```

When printing non-json summary, add:

```python
        print(f"Model estimates: {summary.get('model_estimate_count', 0)}")
        print(f"Usable model estimates: {summary.get('usable_model_estimate_count', 0)}")
```

- [ ] **Step 4: Run CLI shadow tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/cli.py tests/test_cli_shadow.py
git commit -m "feat: default shadow scan to auto fair"
```

## Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/shadow_trading_runbook.md`

- [ ] **Step 1: Update docs**

Update README Shadow Trading Simulation section to show:

```bash
python -m sports_edge_scanner shadow scan --limit 20 --config shadow_config.json --events shadow_events.jsonl
python -m sports_edge_scanner shadow report --events shadow_events.jsonl
```

Explain:

- `--fair` is optional.
- Without `--fair`, the system uses conservative auto fair estimates.
- Low-confidence estimates are audited and do not generate trades.

Update `docs/shadow_trading_runbook.md` to remove the requirement that the operator copy/edit a fair file for normal use. Keep manual fair probabilities as an advanced override.

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_auto_fair.py tests/test_cli_shadow.py tests/test_shadow_reports.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 5: Run local no-manual-file shadow command**

Run:

```bash
python -m sports_edge_scanner shadow scan --limit 1 --config "" --events tmp_auto_shadow_events.jsonl --json
python -m sports_edge_scanner shadow report --events tmp_auto_shadow_events.jsonl --json
```

Expected:

- Command does not require `--fair`.
- Command exits 0 unless public API is unavailable.
- Report includes model estimate fields.

Clean up:

```powershell
Remove-Item -LiteralPath tmp_auto_shadow_events.jsonl -ErrorAction SilentlyContinue
```

- [ ] **Step 6: Review diff**

Run: `git diff --stat`

Expected: only auto fair core, shadow pipeline/state/report tests, CLI, docs, spec, and plan files changed.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/shadow_trading_runbook.md
git commit -m "docs: document automatic fair probabilities"
```
