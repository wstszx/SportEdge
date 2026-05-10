# Shadow Ops Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add operational review tools for shadow trading through the existing dashboard, a public API smoke command, and a runbook.

**Architecture:** Keep Streamlit as the only UI, add pure dashboard-data helpers for shadow report tables, add a dependency-injected public-data smoke helper in the CLI layer, and document the safe operating workflow. No authenticated trading, private keys, or order placement are introduced.

**Tech Stack:** Python 3.10+, standard library, Streamlit optional dashboard dependency, pytest.

---

## File Structure

- Modify `sports_edge_scanner/dashboard_data.py`: include shadow report state and table rows.
- Modify `dashboard_app.py`: add sidebar path for shadow events and a Shadow tab.
- Modify `sports_edge_scanner/cli.py`: add `shadow smoke` command and dependency-injected helper.
- Create `docs/shadow_trading_runbook.md`: operator guide.
- Add/modify tests in `tests/test_dashboard.py`, `tests/test_cli_shadow.py`, and `tests/test_docs.py`.

## Task 1: Dashboard Data Helpers For Shadow Reports

**Files:**
- Modify: `sports_edge_scanner/dashboard_data.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_dashboard.py`:

```python
def sample_shadow_events():
    return [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
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


def test_build_dashboard_state_includes_shadow_report_and_tables():
    state = build_dashboard_state(sample_records(), sample_snapshots(), sample_shadow_events())

    assert state["shadow_report"]["candidate_count"] == 1
    assert state["shadow_exposure_by_market"] == [
        {"market_id": "m1", "exposure": 5.0}
    ]
    assert state["shadow_exposure_by_outcome"] == [
        {"market_outcome": "m1:Team A", "exposure": 5.0}
    ]
    assert state["shadow_risk_decisions"][0]["reasons"] == ["wide spread"]
    assert state["shadow_fills"][0]["outcome_name"] == "Team A"
```

- [ ] **Step 2: Run dashboard tests to verify failure**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: FAIL because `build_dashboard_state` does not accept shadow events.

- [ ] **Step 3: Implement dashboard shadow helpers**

Modify `sports_edge_scanner/dashboard_data.py`:

```python
from sports_edge_scanner.core.shadow_reports import build_shadow_report
```

Add helpers:

```python
def _dict_rows(mapping: dict[str, float], key_name: str) -> list[dict[str, object]]:
    return [
        {key_name: key, "exposure": value}
        for key, value in sorted(mapping.items())
    ]
```

Change `build_dashboard_state` signature:

```python
def build_dashboard_state(
    records: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    shadow_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    shadow_report = build_shadow_report(shadow_events or [])
    return {
        "report": build_report(records, snapshots),
        "quality": build_quality_report(records, snapshots),
        "latest_markets": latest_market_rows(snapshots),
        "paper_trades": paper_trade_rows(records),
        "settlements": settlement_rows(records),
        "shadow_report": shadow_report,
        "shadow_exposure_by_market": _dict_rows(
            shadow_report["exposure_by_market"],
            "market_id",
        ),
        "shadow_exposure_by_outcome": _dict_rows(
            shadow_report["exposure_by_outcome"],
            "market_outcome",
        ),
        "shadow_risk_decisions": shadow_report["risk_decisions"],
        "shadow_fills": shadow_report["fills"],
    }
```

- [ ] **Step 4: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: PASS.

## Task 2: Dashboard Shadow Tab

**Files:**
- Modify: `dashboard_app.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing tests for dashboard text keys**

Append to `tests/test_dashboard.py`:

```python
def test_dashboard_has_shadow_ui_labels():
    assert _label("shadow_tab") == "影子交易"
    assert _label("shadow_events_path") == "影子事件文件"
    assert _label("shadow_quality_clean") == "影子交易数据质量当前无警告。"
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_dashboard.py::test_dashboard_has_shadow_ui_labels -q`

Expected: FAIL because UI labels do not exist.

- [ ] **Step 3: Add labels and imports**

Modify `dashboard_app.py`:

```python
from sports_edge_scanner.core.events import read_events
```

Add `UI_TEXT` keys:

```python
"shadow_tab": "影子交易",
"shadow_events_path": "影子事件文件",
"shadow_overview": "影子交易概览",
"shadow_quality_clean": "影子交易数据质量当前无警告。",
"shadow_exposure_market": "按市场暴露",
"shadow_exposure_outcome": "按结果暴露",
"shadow_risk_decisions": "风控决策",
"shadow_fills": "影子成交",
"shadow_raw_report": "影子原始报告",
```

Add `TABLE_LABELS` keys:

```python
"market_outcome": "市场/结果",
"exposure": "暴露",
"filled_notional": "已成交名义金额",
"unfilled_notional": "未成交名义金额",
"slippage": "滑点",
"allowed": "是否允许",
"reasons": "原因",
```

- [ ] **Step 4: Wire shadow events into state**

Modify `_load_state`:

```python
def _load_state(
    ledger_path: Path,
    snapshot_path: Path,
    shadow_events_path: Path,
) -> tuple[list[dict], list[dict], list[dict], dict]:
    records = read_records(ledger_path)
    snapshots = read_snapshots(snapshot_path)
    shadow_events = read_events(shadow_events_path)
    return records, snapshots, shadow_events, build_dashboard_state(
        records,
        snapshots,
        shadow_events,
    )
```

Update caller:

```python
shadow_events_path = Path(st.text_input(_label("shadow_events_path"), "shadow_events.jsonl"))
records, snapshots, shadow_events, state = _load_state(
    ledger_path,
    snapshot_path,
    shadow_events_path,
)
```

- [ ] **Step 5: Add `_render_shadow`**

Add:

```python
def _render_shadow(state: dict) -> None:
    report = state["shadow_report"]
    st.subheader(_label("shadow_overview"))
    columns = st.columns(6)
    columns[0].metric(_label("candidates"), f"{report['candidate_count']:,}")
    columns[1].metric("Accepted", f"{report['accepted_order_count']:,}")
    columns[2].metric("Rejected", f"{report['rejected_order_count']:,}")
    columns[3].metric("Filled", _money(report["simulated_notional_filled"]))
    columns[4].metric("Unfilled", _money(report["simulated_unfilled_notional"]))
    columns[5].metric("Avg slippage", f"{report['average_slippage']:.4f}")

    if report["data_quality_warnings"]:
        st.warning(" | ".join(report["data_quality_warnings"]))
    else:
        st.success(_label("shadow_quality_clean"))

    st.subheader(_label("shadow_exposure_market"))
    st.dataframe(_display_rows(state["shadow_exposure_by_market"]), use_container_width=True, hide_index=True)
    st.subheader(_label("shadow_exposure_outcome"))
    st.dataframe(_display_rows(state["shadow_exposure_by_outcome"]), use_container_width=True, hide_index=True)
    st.subheader(_label("shadow_risk_decisions"))
    st.dataframe(_display_rows(state["shadow_risk_decisions"]), use_container_width=True, hide_index=True)
    st.subheader(_label("shadow_fills"))
    st.dataframe(_display_rows(state["shadow_fills"]), use_container_width=True, hide_index=True)
    st.subheader(_label("shadow_raw_report"))
    st.json(_localize_json(report))
```

Add Shadow tab to `st.tabs`, then call `_render_shadow(state)`.

- [ ] **Step 6: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: PASS.

## Task 3: Shadow Smoke Command

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_cli_shadow.py`:

```python
from sports_edge_scanner.cli import run_shadow_smoke


def test_parser_supports_shadow_smoke():
    parser = build_parser()

    args = parser.parse_args(["shadow", "smoke", "--limit", "2", "--json"])

    assert args.command == "shadow"
    assert args.shadow_command == "smoke"
    assert args.limit == 2
    assert args.json is True


def test_run_shadow_smoke_reports_success_with_fake_clients():
    result = run_shadow_smoke(
        market_client=FakeMarketClient(),
        book_client=FakeBookClient(),
        limit=2,
    )

    assert result["markets_found"] == 1
    assert result["orderbooks_attempted"] == 2
    assert result["orderbooks_succeeded"] == 2
    assert result["ok"] is True


class EmptyMarketClient:
    def fetch_markets(self, limit):
        return []


def test_run_shadow_smoke_fails_without_markets():
    result = run_shadow_smoke(
        market_client=EmptyMarketClient(),
        book_client=FakeBookClient(),
        limit=2,
    )

    assert result["ok"] is False
    assert "no markets found" in result["warnings"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: FAIL because `run_shadow_smoke` and parser command do not exist.

- [ ] **Step 3: Implement smoke helper**

Add to `sports_edge_scanner/cli.py`:

```python
def run_shadow_smoke(market_client, book_client, limit: int) -> dict[str, object]:
    warnings: list[str] = []
    failures: list[dict[str, str]] = []
    markets = market_client.fetch_markets(limit=limit)
    attempted = 0
    succeeded = 0
    for market in markets:
        for outcome in market.outcomes:
            if not outcome.token_id:
                continue
            attempted += 1
            try:
                book_client.fetch_orderbook(outcome.token_id)
                succeeded += 1
            except Exception as exc:
                failures.append(
                    {
                        "market_id": market.id,
                        "token_id": outcome.token_id,
                        "error": str(exc),
                    }
                )
    if not markets:
        warnings.append("no markets found")
    if attempted == 0 and markets:
        warnings.append("no token ids found")
    if attempted and succeeded == 0:
        warnings.append("all orderbook fetches failed")
    return {
        "ok": bool(markets) and attempted > 0 and succeeded == attempted,
        "markets_found": len(markets),
        "orderbooks_attempted": attempted,
        "orderbooks_succeeded": succeeded,
        "orderbooks_failed": len(failures),
        "warnings": warnings,
        "failures": failures,
    }
```

Add command:

```python
def _shadow_smoke(args: argparse.Namespace) -> int:
    try:
        result = run_shadow_smoke(
            market_client=PolymarketClient(),
            book_client=PolymarketCLOBClient(),
            limit=args.limit,
        )
    except Exception as exc:
        print(f"shadow smoke failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Markets found: {result['markets_found']}")
        print(f"Orderbooks attempted: {result['orderbooks_attempted']}")
        print(f"Orderbooks succeeded: {result['orderbooks_succeeded']}")
        print(f"Orderbooks failed: {result['orderbooks_failed']}")
        if result["warnings"]:
            print(f"Warnings: {', '.join(result['warnings'])}")
    return 0 if result["ok"] else 1
```

Add parser:

```python
shadow_smoke = shadow_subparsers.add_parser(
    "smoke",
    help="Check public Gamma and CLOB data availability without trading.",
)
shadow_smoke.add_argument("--limit", type=int, default=2)
shadow_smoke.add_argument("--json", action="store_true")
shadow_smoke.set_defaults(func=_shadow_smoke)
```

- [ ] **Step 4: Run CLI shadow tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

## Task 4: Runbook

**Files:**
- Create: `docs/shadow_trading_runbook.md`
- Create: `tests/test_docs.py`

- [ ] **Step 1: Add failing docs test**

Create `tests/test_docs.py`:

```python
from pathlib import Path


def test_shadow_trading_runbook_contains_core_commands():
    text = Path("docs/shadow_trading_runbook.md").read_text(encoding="utf-8")

    assert "shadow init-config" in text
    assert "shadow smoke" in text
    assert "shadow scan" in text
    assert "shadow report" in text
    assert "does not place real orders" in text
```

- [ ] **Step 2: Run docs test to verify failure**

Run: `python -m pytest tests/test_docs.py -q`

Expected: FAIL because runbook does not exist.

- [ ] **Step 3: Create runbook**

Create `docs/shadow_trading_runbook.md` with sections:

```markdown
# Shadow Trading Runbook

Sports Edge Scanner shadow mode is a research workflow. It does not place real orders, sign payloads, manage wallets, or control funds.

## 1. Create Starter Files

```bash
python -m sports_edge_scanner shadow init-config
```

This creates `shadow_config.json` and `fair_probabilities.example.json` unless they already exist.

## 2. Add Fair Probabilities

Copy the example file and provide probabilities by market/outcome or token id. Treat these probabilities as model inputs that require independent validation.

## 3. Check Public Data

```bash
python -m sports_edge_scanner shadow smoke --limit 2
```

Use smoke checks before longer scans. Failures mean public market or orderbook data is unavailable or the response shape changed.

## 4. Run A Shadow Scan

```bash
python -m sports_edge_scanner shadow scan --limit 20 --fair fair_probabilities.json --config shadow_config.json --events shadow_events.jsonl
```

Every candidate is either rejected by risk controls or simulated as a limit order against observed orderbook depth.

## 5. Review The Report

```bash
python -m sports_edge_scanner shadow report --events shadow_events.jsonl
```

Review exposure, rejected orders, fills, unfilled notional, average slippage, and data quality warnings.

## 6. Open The Dashboard

```bash
streamlit run dashboard_app.py
```

Set the shadow events path in the sidebar to inspect fills, risk decisions, exposure, and raw report JSON.

## 7. Warnings That Make Results Unreliable

- Stale orderbooks mean pricing may not represent current executable depth.
- Orderbook errors mean the run did not observe all candidate liquidity.
- Missing fills mean candidates did not become simulated executions.
- High unfilled notional means liquidity was insufficient at the configured limits.
- Rejected orders mean risk controls blocked execution and should be reviewed before changing limits.
- Fair probabilities without calibration or sample-size evidence should not be trusted.
```

- [ ] **Step 4: Run docs test**

Run: `python -m pytest tests/test_docs.py -q`

Expected: PASS.

## Task 5: Full Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
python -m pytest tests/test_dashboard.py tests/test_cli_shadow.py tests/test_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 4: Run non-network CLI smoke for report**

Run: `python -m sports_edge_scanner shadow report --events missing-shadow-events.jsonl --json`

Expected: exits 0 and prints an empty report.

- [ ] **Step 5: Review diff**

Run: `git diff --stat`

Expected: only dashboard, CLI, docs, tests, spec, and plan files changed.
