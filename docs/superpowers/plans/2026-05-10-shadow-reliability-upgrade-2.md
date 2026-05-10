# Shadow Reliability Upgrade 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the shadow trading system's maintainability and repeated-run reliability without adding real trading.

**Architecture:** Move shadow orchestration out of the CLI into `core.shadow_pipeline`, derive reporting from replayed event state, add safe config generation, harden public connectors with bounded retries, and expose generic outcomes in legacy scan JSON. Keep all new behavior covered by focused tests and preserve existing command compatibility.

**Tech Stack:** Python 3.10+, standard library only (`argparse`, `dataclasses`, `json`, `pathlib`, `time`, `urllib`), pytest.

---

## File Structure

- Create `sports_edge_scanner/core/shadow_pipeline.py`: extracted shadow scan orchestration.
- Create `sports_edge_scanner/core/shadow_state.py`: replay event logs into reportable state.
- Create `sports_edge_scanner/core/shadow_config.py`: default config and example fair-probability file generation.
- Modify `sports_edge_scanner/core/shadow_reports.py`: build richer reports from state.
- Modify `sports_edge_scanner/connectors/polymarket.py`: add retry and payload validation.
- Modify `sports_edge_scanner/connectors/polymarket_clob.py`: add retry and orderbook payload validation.
- Modify `sports_edge_scanner/cli.py`: import pipeline/config helpers, remove pipeline internals, add `shadow init-config`.
- Modify `README.md`: document init-config and richer report behavior.
- Modify tests and add new focused tests.

## Task 1: Extract Shadow Pipeline From CLI

**Files:**
- Create: `sports_edge_scanner/core/shadow_pipeline.py`
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Change pipeline imports in tests**

Update `tests/test_cli_shadow.py` so `run_shadow_scan` is imported from the new module:

```python
from sports_edge_scanner.cli import build_parser
from sports_edge_scanner.core.shadow_pipeline import run_shadow_scan
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'sports_edge_scanner.core.shadow_pipeline'`.

- [ ] **Step 3: Create pipeline module**

Create `sports_edge_scanner/core/shadow_pipeline.py` with the existing helper functions and `run_shadow_scan` currently in `cli.py`:

```python
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sports_edge_scanner.core.events import append_event, make_event
from sports_edge_scanner.core.fair import FairProbabilityBook
from sports_edge_scanner.core.risk import RiskConfig, evaluate_candidate_order
from sports_edge_scanner.core.shadow_execution import simulate_buy_limit_fill
from sports_edge_scanner.core.shadow_signals import candidate_orders_for_market
from sports_edge_scanner.models import OrderBook, ShadowOrder


def _order_id(run_id: str, index: int) -> str:
    return f"{run_id}-shadow-{index}"


def _parse_iso_datetime(value: str) -> datetime | None:
    text = value
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _orderbook_age_seconds(orderbook: OrderBook, now: datetime) -> float | None:
    parsed = _parse_iso_datetime(orderbook.timestamp)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds())


def run_shadow_scan(
    market_client: Any,
    book_client: Any,
    fair_book: FairProbabilityBook,
    risk_config: RiskConfig,
    limit: int,
    events_path: Path,
    run_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    markets = market_client.fetch_markets(limit=limit)
    candidate_count = 0
    accepted_count = 0
    rejected_count = 0
    order_index = 0
    market_exposure: dict[str, float] = {}
    total_exposure = 0.0
    current_time = now or datetime.now(timezone.utc)

    for market in markets:
        books: dict[str, OrderBook] = {}
        for outcome in market.outcomes:
            if outcome.token_id:
                try:
                    book = book_client.fetch_orderbook(outcome.token_id)
                    books[outcome.token_id] = book
                    append_event(
                        events_path,
                        make_event(
                            "orderbook_snapshot",
                            run_id,
                            {
                                "market_id": market.id,
                                "token_id": outcome.token_id,
                                **book.to_dict(),
                            },
                        ),
                    )
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
            projected_order = ShadowOrder(
                order_id=_order_id(run_id, order_index + 1),
                market_id=candidate.market_id,
                outcome_name=candidate.outcome_name,
                token_id=candidate.token_id,
                side="BUY",
                limit_price=candidate.limit_price,
                notional=min(
                    candidate.requested_notional,
                    risk_config.max_order_notional,
                    max(
                        0.0,
                        risk_config.max_market_exposure
                        - market_exposure.get(candidate.market_id, 0.0),
                    ),
                    max(0.0, risk_config.max_total_exposure - total_exposure),
                ),
                source_signal_id=f"{run_id}-signal-{candidate_count}",
            )
            simulated_fill = simulate_buy_limit_fill(projected_order, book)
            decision = evaluate_candidate_order(
                candidate,
                book,
                risk_config,
                market_exposure=market_exposure.get(candidate.market_id, 0.0),
                total_exposure=total_exposure,
                daily_pnl=0.0,
                market_liquidity=market.liquidity,
                orderbook_age_seconds=_orderbook_age_seconds(book, current_time),
                simulated_fill=simulated_fill,
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
            market_exposure[candidate.market_id] = (
                market_exposure.get(candidate.market_id, 0.0) + decision.approved_notional
            )
            total_exposure += decision.approved_notional
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
                        "outcome_name": candidate.outcome_name,
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

- [ ] **Step 4: Thin CLI imports and remove duplicated helpers**

In `sports_edge_scanner/cli.py`, import `run_shadow_scan` from `sports_edge_scanner.core.shadow_pipeline`, remove `datetime`, `timezone`, `OrderBook`, `ShadowOrder`, `append_event`, `make_event`, `evaluate_candidate_order`, `simulate_buy_limit_fill`, and `candidate_orders_for_market` imports if unused, and delete local `_order_id`, `_parse_iso_datetime`, `_orderbook_age_seconds`, and local `run_shadow_scan`.

- [ ] **Step 5: Run CLI shadow tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

## Task 2: Shadow State Replay

**Files:**
- Create: `sports_edge_scanner/core/shadow_state.py`
- Test: `tests/test_shadow_state.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_shadow_state.py`:

```python
import pytest

from sports_edge_scanner.core.shadow_state import build_shadow_state


def test_build_shadow_state_replays_fills_rejections_and_exposure():
    events = [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {"event_type": "orderbook_error", "market_id": "m2", "token_id": "t2"},
        {
            "event_type": "risk_decision",
            "allowed": False,
            "market_id": "m1",
            "reasons": ["wide spread", "low liquidity"],
        },
        {
            "event_type": "risk_decision",
            "allowed": True,
            "market_id": "m1",
            "token_id": "t1",
            "approved_notional": 10.0,
            "reasons": ["allowed"],
        },
        {
            "event_type": "shadow_fill",
            "market_id": "m1",
            "outcome_name": "Team A",
            "token_id": "t1",
            "status": "partial",
            "filled_notional": 6.0,
            "unfilled_notional": 4.0,
            "slippage": 0.02,
        },
    ]

    state = build_shadow_state(events)

    assert state["candidate_count"] == 1
    assert state["accepted_order_count"] == 1
    assert state["rejected_order_count"] == 1
    assert state["orderbook_error_count"] == 1
    assert state["simulated_notional_filled"] == 6.0
    assert state["simulated_unfilled_notional"] == 4.0
    assert state["average_slippage"] == pytest.approx(0.02)
    assert state["rejections_by_reason"] == {"wide spread": 1, "low liquidity": 1}
    assert state["exposure_by_market"] == {"m1": 6.0}
    assert state["exposure_by_outcome"] == {"m1:Team A": 6.0}
    assert state["fill_status_counts"] == {"partial": 1}
    assert state["fills"][0]["outcome_name"] == "Team A"
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_shadow_state.py -q`

Expected: FAIL because `sports_edge_scanner.core.shadow_state` does not exist.

- [ ] **Step 3: Implement state replay**

Create `sports_edge_scanner/core/shadow_state.py`:

```python
from typing import Any


def build_shadow_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_count = 0
    accepted_order_count = 0
    rejected_order_count = 0
    orderbook_error_count = 0
    rejections_by_reason: dict[str, int] = {}
    fill_status_counts: dict[str, int] = {}
    exposure_by_market: dict[str, float] = {}
    exposure_by_outcome: dict[str, float] = {}
    fills: list[dict[str, Any]] = []
    filled_notional = 0.0
    unfilled_notional = 0.0
    slippages: list[float] = []
    risk_decisions: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type")
        if event_type == "signal" and event.get("status") == "candidate":
            candidate_count += 1
        elif event_type == "orderbook_error":
            orderbook_error_count += 1
        elif event_type == "risk_decision":
            risk_decisions.append(event)
            if event.get("allowed"):
                accepted_order_count += 1
            else:
                rejected_order_count += 1
                for reason in event.get("reasons") or []:
                    reason_text = str(reason)
                    rejections_by_reason[reason_text] = (
                        rejections_by_reason.get(reason_text, 0) + 1
                    )
        elif event_type == "shadow_fill":
            status = str(event.get("status") or "unknown")
            market_id = str(event.get("market_id") or "")
            outcome_name = str(event.get("outcome_name") or event.get("token_id") or "")
            fill_notional = float(event.get("filled_notional") or 0.0)
            unfilled = float(event.get("unfilled_notional") or 0.0)
            fill_status_counts[status] = fill_status_counts.get(status, 0) + 1
            filled_notional += fill_notional
            unfilled_notional += unfilled
            slippages.append(float(event.get("slippage") or 0.0))
            if market_id and fill_notional:
                exposure_by_market[market_id] = exposure_by_market.get(market_id, 0.0) + fill_notional
                exposure_key = f"{market_id}:{outcome_name}"
                exposure_by_outcome[exposure_key] = exposure_by_outcome.get(exposure_key, 0.0) + fill_notional
            fills.append(event)

    return {
        "candidate_count": candidate_count,
        "accepted_order_count": accepted_order_count,
        "rejected_order_count": rejected_order_count,
        "orderbook_error_count": orderbook_error_count,
        "simulated_notional_filled": filled_notional,
        "simulated_unfilled_notional": unfilled_notional,
        "average_slippage": sum(slippages) / len(slippages) if slippages else 0.0,
        "fill_status_counts": fill_status_counts,
        "rejections_by_reason": rejections_by_reason,
        "exposure_by_market": exposure_by_market,
        "exposure_by_outcome": exposure_by_outcome,
        "risk_decisions": risk_decisions,
        "fills": fills,
    }
```

- [ ] **Step 4: Run state tests**

Run: `python -m pytest tests/test_shadow_state.py -q`

Expected: PASS.

## Task 3: Rich Shadow Reports

**Files:**
- Modify: `sports_edge_scanner/core/shadow_reports.py`
- Modify: `tests/test_shadow_reports.py`

- [ ] **Step 1: Extend report tests**

Update `tests/test_shadow_reports.py` to assert richer fields:

```python
def test_shadow_report_includes_state_and_data_quality_warnings():
    events = [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {"event_type": "orderbook_error", "market_id": "m2", "token_id": "t2"},
        {"event_type": "risk_decision", "allowed": False, "reasons": ["wide spread"]},
        {
            "event_type": "shadow_fill",
            "market_id": "m1",
            "outcome_name": "Team A",
            "status": "partial",
            "filled_notional": 5.0,
            "unfilled_notional": 3.0,
            "slippage": 0.02,
        },
    ]

    report = build_shadow_report(events)

    assert report["orderbook_error_count"] == 1
    assert report["simulated_unfilled_notional"] == 3.0
    assert report["exposure_by_market"] == {"m1": 5.0}
    assert report["exposure_by_outcome"] == {"m1:Team A": 5.0}
    assert "orderbook errors present" in report["data_quality_warnings"]
    assert "rejected orders present" in report["data_quality_warnings"]
    assert "unfilled shadow orders present" in report["data_quality_warnings"]
```

- [ ] **Step 2: Run report tests to verify failure**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: FAIL because rich fields are missing.

- [ ] **Step 3: Implement report from shadow state**

Modify `sports_edge_scanner/core/shadow_reports.py`:

```python
from typing import Any

from sports_edge_scanner.core.shadow_state import build_shadow_state


def _warnings(state: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if state["orderbook_error_count"]:
        warnings.append("orderbook errors present")
    if state["rejected_order_count"]:
        warnings.append("rejected orders present")
    if state["simulated_unfilled_notional"]:
        warnings.append("unfilled shadow orders present")
    if state["candidate_count"] and not state["simulated_notional_filled"]:
        warnings.append("candidates present but no fills")
    return warnings


def build_shadow_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    state = build_shadow_state(events)
    return {
        **state,
        "data_quality_warnings": _warnings(state),
    }
```

- [ ] **Step 4: Run report tests**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: PASS.

## Task 4: Config Template Generation

**Files:**
- Create: `sports_edge_scanner/core/shadow_config.py`
- Modify: `sports_edge_scanner/cli.py`
- Test: `tests/test_shadow_config.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Write config tests**

Create `tests/test_shadow_config.py`:

```python
import json

import pytest

from sports_edge_scanner.core.shadow_config import (
    default_fair_probability_example,
    default_risk_config_dict,
    write_shadow_config_templates,
)


def test_default_risk_config_dict_matches_safe_defaults():
    config = default_risk_config_dict()

    assert config["max_order_notional"] == 10.0
    assert config["max_total_exposure"] == 100.0
    assert config["stale_book_seconds"] == 30


def test_write_shadow_config_templates_refuses_overwrite_without_force(tmp_path):
    config_path = tmp_path / "shadow_config.json"
    fair_path = tmp_path / "fair_probabilities.example.json"
    config_path.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_shadow_config_templates(config_path, fair_path, force=False)


def test_write_shadow_config_templates_writes_files(tmp_path):
    config_path = tmp_path / "shadow_config.json"
    fair_path = tmp_path / "fair_probabilities.example.json"

    written = write_shadow_config_templates(config_path, fair_path, force=False)

    assert written == [config_path, fair_path]
    assert json.loads(config_path.read_text(encoding="utf-8"))["max_order_notional"] == 10.0
    assert json.loads(fair_path.read_text(encoding="utf-8")) == default_fair_probability_example()
```

- [ ] **Step 2: Run config tests to verify failure**

Run: `python -m pytest tests/test_shadow_config.py -q`

Expected: FAIL because `shadow_config` does not exist.

- [ ] **Step 3: Implement shadow config helpers**

Create `sports_edge_scanner/core/shadow_config.py`:

```python
import json
from dataclasses import asdict
from pathlib import Path

from sports_edge_scanner.core.risk import RiskConfig


def default_risk_config_dict() -> dict[str, float | int]:
    return asdict(RiskConfig())


def default_fair_probability_example() -> dict[str, object]:
    return {
        "markets": {
            "example-market-slug": {
                "Team A": 0.57,
            }
        },
        "tokens": {
            "example-token-id": 0.57,
        },
    }


def _write_json(path: Path, payload: dict[str, object], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_shadow_config_templates(
    config_path: Path,
    fair_path: Path,
    force: bool = False,
) -> list[Path]:
    _write_json(config_path, default_risk_config_dict(), force=force)
    _write_json(fair_path, default_fair_probability_example(), force=force)
    return [config_path, fair_path]
```

- [ ] **Step 4: Add CLI parser test for init-config**

Update `tests/test_cli_shadow.py`:

```python
def test_parser_supports_shadow_init_config():
    parser = build_parser()

    args = parser.parse_args(
        [
            "shadow",
            "init-config",
            "--config",
            "custom_config.json",
            "--fair",
            "custom_fair.json",
            "--force",
        ]
    )

    assert args.command == "shadow"
    assert args.shadow_command == "init-config"
    assert args.config == "custom_config.json"
    assert args.fair == "custom_fair.json"
    assert args.force is True
```

- [ ] **Step 5: Run CLI shadow test to verify failure**

Run: `python -m pytest tests/test_cli_shadow.py::test_parser_supports_shadow_init_config -q`

Expected: FAIL because parser lacks `init-config`.

- [ ] **Step 6: Implement CLI command**

In `sports_edge_scanner/cli.py`, import:

```python
from sports_edge_scanner.core.shadow_config import write_shadow_config_templates
```

Add command function:

```python
def _shadow_init_config(args: argparse.Namespace) -> int:
    try:
        written = write_shadow_config_templates(
            Path(args.config),
            Path(args.fair),
            force=args.force,
        )
    except FileExistsError as exc:
        print(f"shadow init-config failed: {exc}", file=sys.stderr)
        return 2

    for path in written:
        print(f"wrote {path}")
    return 0
```

Add parser under `shadow_subparsers`:

```python
    shadow_init = shadow_subparsers.add_parser(
        "init-config",
        help="Write safe shadow config and fair-probability example files.",
    )
    shadow_init.add_argument("--config", default="shadow_config.json")
    shadow_init.add_argument("--fair", default="fair_probabilities.example.json")
    shadow_init.add_argument("--force", action="store_true")
    shadow_init.set_defaults(func=_shadow_init_config)
```

- [ ] **Step 7: Run config and CLI tests**

Run: `python -m pytest tests/test_shadow_config.py tests/test_cli_shadow.py -q`

Expected: PASS.

## Task 5: Connector Retry And Shape Validation

**Files:**
- Modify: `sports_edge_scanner/connectors/polymarket.py`
- Modify: `sports_edge_scanner/connectors/polymarket_clob.py`
- Modify: `tests/test_polymarket_connector.py`
- Modify: `tests/test_polymarket_clob.py`

- [ ] **Step 1: Add Polymarket retry and invalid payload tests**

Append to `tests/test_polymarket_connector.py`:

```python
def test_fetch_markets_retries_after_transient_failure(monkeypatch):
    calls = {"count": 0}
    payload = [
        {
            "id": "sports",
            "question": "Will the Lakers win?",
            "active": True,
            "closed": False,
            "outcomes": '["YES", "NO"]',
            "outcomePrices": '["0.47", "0.52"]',
        }
    ]

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary network error")
        return FakeResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketClient(retry_delay_seconds=0.0).fetch_markets(limit=1)

    assert calls["count"] == 2
    assert len(markets) == 1


def test_fetch_markets_rejects_invalid_payload_shape(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"unexpected": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    try:
        PolymarketClient(retry_delay_seconds=0.0).fetch_markets(limit=1)
        raised = False
    except ValueError as exc:
        raised = "markets response" in str(exc)

    assert raised is True
```

- [ ] **Step 2: Run Polymarket tests to verify failure**

Run: `python -m pytest tests/test_polymarket_connector.py -q`

Expected: FAIL because constructor lacks retry delay and invalid shape is not rejected.

- [ ] **Step 3: Implement retry helper in `polymarket.py`**

Modify `PolymarketClient.__init__`:

```python
def __init__(
    self,
    base_url: str = "https://gamma-api.polymarket.com",
    attempts: int = 2,
    retry_delay_seconds: float = 0.25,
) -> None:
    self.base_url = base_url.rstrip("/")
    self.attempts = max(1, attempts)
    self.retry_delay_seconds = max(0.0, retry_delay_seconds)
```

Add `import time`.

Add helper:

```python
def _raw_markets_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("markets"), list):
            return payload["markets"]
        if isinstance(payload.get("data"), list):
            return payload["data"]
    raise ValueError("markets response must be a list or contain markets/data list")
```

Replace payload extraction in `fetch_markets` with retry loop:

```python
last_error: Exception | None = None
for attempt in range(self.attempts):
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        raw_markets = _raw_markets_from_payload(payload)
        break
    except Exception as exc:
        last_error = exc
        if attempt < self.attempts - 1:
            time.sleep(self.retry_delay_seconds)
else:
    assert last_error is not None
    raise last_error
```

- [ ] **Step 4: Add CLOB retry and validation tests**

Append to `tests/test_polymarket_clob.py`:

```python
def test_fetch_orderbook_retries_after_transient_failure(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary network error")
        return FakeResponse(
            {
                "market": "market-1",
                "asset_id": "token-a",
                "bids": [],
                "asks": [{"price": "0.47", "size": "10"}],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    book = PolymarketCLOBClient(retry_delay_seconds=0.0).fetch_orderbook("token-a")

    assert calls["count"] == 2
    assert book.best_ask == 0.47


def test_fetch_orderbook_rejects_missing_token_identity():
    try:
        normalize_orderbook({"market": "market-1", "bids": [], "asks": []}, fallback_token_id="")
        raised = False
    except ValueError as exc:
        raised = "token id" in str(exc)

    assert raised is True
```

- [ ] **Step 5: Run CLOB tests to verify failure**

Run: `python -m pytest tests/test_polymarket_clob.py -q`

Expected: FAIL because retry args and token validation are missing.

- [ ] **Step 6: Implement CLOB retry and validation**

Modify `sports_edge_scanner/connectors/polymarket_clob.py`:

```python
import time
```

In `normalize_orderbook`, compute token id and validate:

```python
token_id = str(payload.get("asset_id") or payload.get("token_id") or fallback_token_id)
if not token_id:
    raise ValueError("orderbook response missing token id")
```

Modify class constructor:

```python
def __init__(
    self,
    base_url: str = "https://clob.polymarket.com",
    attempts: int = 2,
    retry_delay_seconds: float = 0.25,
) -> None:
    self.base_url = base_url.rstrip("/")
    self.attempts = max(1, attempts)
    self.retry_delay_seconds = max(0.0, retry_delay_seconds)
```

Wrap fetch body in a retry loop like PolymarketClient.

- [ ] **Step 7: Run connector tests**

Run: `python -m pytest tests/test_polymarket_connector.py tests/test_polymarket_clob.py -q`

Expected: PASS.

## Task 6: Generic Outcomes In Legacy Scan JSON

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failing test for generic outcomes**

Append to `tests/test_cli.py`:

```python
def test_market_snapshot_includes_generic_outcomes():
    snapshot = market_snapshot(make_market())

    assert snapshot["outcomes"] == [
        {"name": "YES", "price": 0.47, "token_id": None},
        {"name": "NO", "price": 0.52, "token_id": None},
    ]
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_cli.py::test_market_snapshot_includes_generic_outcomes -q`

Expected: FAIL because `outcomes` is missing.

- [ ] **Step 3: Add outcomes to snapshot**

Modify `market_snapshot` in `sports_edge_scanner/cli.py` to include:

```python
"outcomes": [
    {
        "name": outcome.name,
        "price": outcome.price,
        "token_id": outcome.token_id,
    }
    for outcome in market.outcomes
],
```

- [ ] **Step 4: Run CLI tests**

Run: `python -m pytest tests/test_cli.py -q`

Expected: PASS.

## Task 7: README And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document init-config**

Add to the Shadow Trading Simulation section:

```markdown
Create safe starter files:

```bash
python -m sports_edge_scanner shadow init-config
```

This writes `shadow_config.json` and `fair_probabilities.example.json` unless they already exist. Use `--force` only when you intentionally want to overwrite them.
```

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_cli_shadow.py tests/test_shadow_state.py tests/test_shadow_reports.py tests/test_shadow_config.py tests/test_polymarket_connector.py tests/test_polymarket_clob.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run CLI smoke checks**

Run:

```bash
python -m sports_edge_scanner shadow report --events missing-shadow-events.jsonl --json
python -m sports_edge_scanner shadow init-config --config .tmp-shadow-config.json --fair .tmp-fair.json
python -m sports_edge_scanner --help
```

Expected: all commands exit 0; remove `.tmp-shadow-config.json` and `.tmp-fair.json` after smoke check.

- [ ] **Step 5: Review diff**

Run: `git diff --stat`

Expected: only planned source, tests, README, spec, and plan files changed.

