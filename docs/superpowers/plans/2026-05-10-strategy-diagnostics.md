# Strategy Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strategy diagnostics that explain why shadow mode has insufficient fills and what conservative next action is required.

**Architecture:** Add `sports_edge_scanner.core.strategy_diagnostics` as a pure evaluator over shadow reports. Attach diagnostics in `build_shadow_report`, localize/display them in `dashboard_app.py`, and keep readiness as the only gate.

**Tech Stack:** Python 3.10+, dataclasses, existing shadow report dictionaries, pytest.

---

## File Structure

- Create `sports_edge_scanner/core/strategy_diagnostics.py`: diagnostic evaluator.
- Create `tests/test_strategy_diagnostics.py`: evaluator tests.
- Modify `sports_edge_scanner/core/shadow_reports.py`: attach diagnostics.
- Modify `tests/test_shadow_reports.py`: report integration test.
- Modify `dashboard_app.py`: labels, translations, diagnostics display.
- Modify `tests/test_dashboard.py`: label/translation tests.

## Task 1: Pure Strategy Diagnostics

**Files:**
- Create: `sports_edge_scanner/core/strategy_diagnostics.py`
- Create: `tests/test_strategy_diagnostics.py`

- [ ] **Step 1: Write failing evaluator tests**

Cover collecting data, needs independent signal, needs execution samples, execution quality issue, and healthy status.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_strategy_diagnostics.py -q`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement evaluator**

Add `evaluate_strategy_diagnostics(report, readiness_config=None)`.

- [ ] **Step 4: Run evaluator tests**

Run: `python -m pytest tests/test_strategy_diagnostics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/strategy_diagnostics.py tests/test_strategy_diagnostics.py
git commit -m "feat: add strategy diagnostics evaluator"
```

## Task 2: Attach Diagnostics To Shadow Report

**Files:**
- Modify: `sports_edge_scanner/core/shadow_reports.py`
- Modify: `tests/test_shadow_reports.py`

- [ ] **Step 1: Add failing report integration test**

Assert `build_shadow_report([])` includes `strategy_diagnostics`.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_shadow_reports.py::test_shadow_report_includes_strategy_diagnostics -q`

Expected: FAIL.

- [ ] **Step 3: Attach diagnostics**

Call evaluator after readiness is attached.

- [ ] **Step 4: Run report tests**

Run: `python -m pytest tests/test_shadow_reports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/shadow_reports.py tests/test_shadow_reports.py
git commit -m "feat: include strategy diagnostics in shadow reports"
```

## Task 3: Dashboard Display

**Files:**
- Modify: `dashboard_app.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing label/translation tests**

Assert dashboard labels and translations include strategy diagnostics terms.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_dashboard.py::test_dashboard_has_strategy_diagnostics_labels -q`

Expected: FAIL.

- [ ] **Step 3: Render diagnostics**

Add `_render_strategy_diagnostics(report)` and call it from Shadow and Control tabs.

- [ ] **Step 4: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard_app.py tests/test_dashboard.py
git commit -m "feat: show strategy diagnostics in dashboard"
```

## Task 4: Verification

- [ ] **Step 1: Run targeted tests**

Run:

```bash
python -m pytest tests/test_strategy_diagnostics.py tests/test_shadow_reports.py tests/test_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 4: Push main**

Run: `git push origin main`
