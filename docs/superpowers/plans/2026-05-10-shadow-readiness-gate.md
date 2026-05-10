# Shadow Readiness Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automatic readiness verdict to shadow reports so the system tells the operator whether paper evidence is adequate for the next review stage.

**Architecture:** Add a focused `sports_edge_scanner.core.shadow_readiness` module that evaluates an existing shadow report using conservative threshold defaults. Extend shadow state with distinct run counts, attach readiness in `build_shadow_report`, and print the verdict in CLI text output.

**Tech Stack:** Python 3.10+, dataclasses, existing JSON report dictionaries, pytest.

---

## File Structure

- Create `sports_edge_scanner/core/shadow_readiness.py`: readiness config and evaluator.
- Create `tests/test_shadow_readiness.py`: evaluator tests.
- Modify `sports_edge_scanner/core/shadow_state.py`: count distinct run ids.
- Modify `sports_edge_scanner/core/shadow_reports.py`: attach readiness section.
- Modify `sports_edge_scanner/cli.py`: print readiness status and blockers in `shadow report`.
- Modify `tests/test_shadow_state.py`, `tests/test_shadow_reports.py`, and `tests/test_cli_shadow.py`.
- Modify `README.md` and `docs/shadow_trading_runbook.md`.

## Task 1: Readiness Evaluator

**Files:**
- Create: `sports_edge_scanner/core/shadow_readiness.py`
- Create: `tests/test_shadow_readiness.py`

- [ ] **Step 1: Write failing evaluator tests**

Create tests for:

- empty report is not ready;
- clean report is ready when thresholds are satisfied;
- low usable-estimate rate blocks readiness;
- execution/data-quality problems block readiness.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_shadow_readiness.py -q`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement evaluator**

Add:

- `ShadowReadinessConfig`
- `evaluate_shadow_readiness(report, config=None)`

Return dictionary with `ready`, `blockers`, `warnings`, `metrics`, and `thresholds`.

- [ ] **Step 4: Run evaluator tests**

Run: `python -m pytest tests/test_shadow_readiness.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add sports_edge_scanner/core/shadow_readiness.py tests/test_shadow_readiness.py
git commit -m "feat: add shadow readiness evaluator"
```

## Task 2: Count Distinct Shadow Runs

**Files:**
- Modify: `sports_edge_scanner/core/shadow_state.py`
- Modify: `tests/test_shadow_state.py`

- [ ] **Step 1: Add failing run count test**

Add a test proving `build_shadow_state` returns `run_count` and sorted `run_ids` from distinct non-empty `run_id` values.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_shadow_state.py::test_build_shadow_state_counts_distinct_run_ids -q`

Expected: FAIL because fields do not exist.

- [ ] **Step 3: Implement run count**

Track non-empty `run_id` values while replaying events and include:

- `run_count`
- `run_ids`

- [ ] **Step 4: Run state tests**

Run: `python -m pytest tests/test_shadow_state.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add sports_edge_scanner/core/shadow_state.py tests/test_shadow_state.py
git commit -m "feat: count shadow run ids"
```

## Task 3: Attach Readiness To Shadow Report

**Files:**
- Modify: `sports_edge_scanner/core/shadow_reports.py`
- Modify: `tests/test_shadow_reports.py`

- [ ] **Step 1: Add failing report test**

Add a test proving `build_shadow_report` includes `readiness.ready`, `readiness.blockers`, `readiness.metrics`, and `readiness.thresholds`.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_shadow_reports.py::test_shadow_report_includes_readiness_section -q`

Expected: FAIL because readiness is not attached.

- [ ] **Step 3: Attach readiness**

Import `evaluate_shadow_readiness`, build report dictionary first, then attach:

```python
report["readiness"] = evaluate_shadow_readiness(report)
```

- [ ] **Step 4: Run report tests**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add sports_edge_scanner/core/shadow_reports.py tests/test_shadow_reports.py
git commit -m "feat: include shadow readiness in reports"
```

## Task 4: CLI Text Output

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli_shadow.py`

- [ ] **Step 1: Add failing CLI output test**

Add a test using a temporary event file and `_shadow_report` to assert non-JSON text includes `Readiness:` and blocking reasons.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_cli_shadow.py::test_shadow_report_text_prints_readiness -q`

Expected: FAIL because text output does not print readiness.

- [ ] **Step 3: Update CLI text report**

Print:

- `Readiness: READY` or `Readiness: NOT READY`
- `Readiness blockers: ...` when blockers exist

- [ ] **Step 4: Run CLI tests**

Run: `python -m pytest tests/test_cli_shadow.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add sports_edge_scanner/cli.py tests/test_cli_shadow.py
git commit -m "feat: print shadow readiness verdict"
```

## Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/shadow_trading_runbook.md`

- [ ] **Step 1: Update docs**

Document that `shadow report` now includes an automatic readiness verdict and that `ready: true` means "adequate paper evidence for next design review", not permission for live trading.

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_shadow_readiness.py tests/test_shadow_state.py tests/test_shadow_reports.py tests/test_cli_shadow.py tests/test_docs.py -q
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
python -m sports_edge_scanner shadow report --events does_not_exist_shadow_events.jsonl --json
```

Expected: JSON includes `readiness.ready` false and blockers.

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md docs/shadow_trading_runbook.md
git commit -m "docs: document shadow readiness gate"
```
