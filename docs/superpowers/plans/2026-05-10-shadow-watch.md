# Shadow Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded `shadow watch` command that repeatedly runs shadow scans, records failures as events, and prints final readiness.

**Architecture:** Add a focused `sports_edge_scanner.core.shadow_watch` module for the reusable loop. Keep scan details in CLI closures that call existing `run_shadow_scan`; extend state/readiness to treat scan failures as blockers; add CLI parser and output.

**Tech Stack:** Python 3.10+, existing JSONL event helpers, existing shadow scan/report modules, pytest.

---

## File Structure

- Create `sports_edge_scanner/core/shadow_watch.py`: bounded watch loop.
- Create `tests/test_shadow_watch.py`: core loop tests.
- Modify `sports_edge_scanner/core/shadow_state.py`: count `shadow_scan_error`.
- Modify `sports_edge_scanner/core/shadow_readiness.py`: block on scan errors.
- Modify `sports_edge_scanner/cli.py`: add `shadow watch`.
- Modify `tests/test_shadow_state.py`, `tests/test_shadow_readiness.py`, `tests/test_cli_shadow.py`.
- Modify `README.md` and `docs/shadow_trading_runbook.md`.

## Task 1: Core Watch Loop

**Files:**
- Create: `sports_edge_scanner/core/shadow_watch.py`
- Create: `tests/test_shadow_watch.py`

- [ ] **Step 1: Write failing tests**

Tests:

- runs requested iterations;
- sleeps only between iterations;
- rejects invalid iteration and interval values;
- continues after a scan failure and appends `shadow_scan_error`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_shadow_watch.py -q`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement watch loop**

Implement `run_shadow_watch(scan_once, build_report, events_path, iterations, interval_seconds, sleep=time.sleep)`.

- [ ] **Step 4: Run watch tests**

Run: `python -m pytest tests/test_shadow_watch.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/shadow_watch.py tests/test_shadow_watch.py
git commit -m "feat: add shadow watch loop"
```

## Task 2: Report Scan Failures And Readiness Blocker

**Files:**
- Modify: `sports_edge_scanner/core/shadow_state.py`
- Modify: `sports_edge_scanner/core/shadow_readiness.py`
- Modify: `tests/test_shadow_state.py`
- Modify: `tests/test_shadow_readiness.py`

- [ ] **Step 1: Add failing tests**

Add tests proving:

- `build_shadow_state` counts `shadow_scan_error` events;
- readiness blocks when `shadow_scan_error_count > 0`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_shadow_state.py::test_build_shadow_state_counts_shadow_scan_errors tests/test_shadow_readiness.py::test_scan_errors_block_readiness -q
```

Expected: FAIL.

- [ ] **Step 3: Implement state/readiness changes**

Add `shadow_scan_error_count` to state and readiness metrics/blockers.

- [ ] **Step 4: Run targeted tests**

Run: `python -m pytest tests/test_shadow_state.py tests/test_shadow_readiness.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/shadow_state.py sports_edge_scanner/core/shadow_readiness.py tests/test_shadow_state.py tests/test_shadow_readiness.py
git commit -m "feat: block readiness on shadow scan errors"
```

## Task 3: CLI Shadow Watch

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Add failing CLI tests**

Tests:

- parser supports `shadow watch`;
- text output prints completed/successful/failed iterations and readiness.

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
python -m pytest tests/test_cli_shadow.py::test_parser_supports_shadow_watch tests/test_cli_shadow.py::test_shadow_watch_text_prints_summary_and_readiness -q
```

Expected: FAIL.

- [ ] **Step 3: Implement CLI**

Add `_shadow_watch(args)` using existing clients/config loaders and `run_shadow_watch`.

Add parser subcommand:

```bash
shadow watch --limit 20 --iterations 20 --interval-seconds 1800 --events shadow_events.jsonl
```

- [ ] **Step 4: Run CLI tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/cli.py tests/test_cli_shadow.py
git commit -m "feat: add shadow watch cli"
```

## Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/shadow_trading_runbook.md`

- [ ] **Step 1: Update docs**

Document `shadow watch`, bounded runs, failure events, and final readiness.

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_shadow_watch.py tests/test_shadow_state.py tests/test_shadow_readiness.py tests/test_cli_shadow.py tests/test_docs.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 5: Run CLI smoke**

Run:

```bash
python -m sports_edge_scanner shadow watch --limit 1 --iterations 1 --interval-seconds 0 --events tmp_shadow_watch_events.jsonl --json
```

Expected: command exits 0 unless public API is unavailable; failures should be represented in JSON and events.

- [ ] **Step 6: Commit docs**

```bash
git add README.md docs/shadow_trading_runbook.md
git commit -m "docs: document shadow watch"
```
