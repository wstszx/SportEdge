# Dashboard Operator Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move paper/shadow collection controls into the dashboard so the recommended operator flow is one startup command: `python -m sports_edge_scanner app`.

**Architecture:** Extend `dashboard_app.py` with testable helper functions that build `_shadow_watch` arguments and run a bounded shadow collection through an injected runner. Add a Control tab that exposes short bounded collection and live safety status while preserving all existing reporting tabs.

**Tech Stack:** Streamlit dashboard, existing CLI shadow watch, pytest.

---

## File Structure

- Modify `dashboard_app.py`: labels, helper functions, control tab rendering.
- Modify `tests/test_dashboard.py`: helper and label tests.
- Modify `README.md`: single-command operator flow.

## Task 1: Dashboard Helper Functions

**Files:**
- Modify: `dashboard_app.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing helper tests**

Tests:

- `build_shadow_watch_args` maps UI values into an argparse namespace for `_shadow_watch`.
- `run_dashboard_shadow_watch` calls injected runner and returns its exit code.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_dashboard.py::test_build_shadow_watch_args_maps_ui_values tests/test_dashboard.py::test_run_dashboard_shadow_watch_uses_injected_runner -q`

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement helpers**

Add:

- `build_shadow_watch_args(...)`
- `run_dashboard_shadow_watch(..., runner=_shadow_watch)`

- [ ] **Step 4: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard_app.py tests/test_dashboard.py
git commit -m "feat: add dashboard shadow control helpers"
```

## Task 2: Control Tab UI

**Files:**
- Modify: `dashboard_app.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing label tests**

Tests:

- control tab label exists.
- run shadow collection labels exist.
- live safety label exists.
- translations include readiness and scan error.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_dashboard.py::test_dashboard_has_control_ui_labels -q`

Expected: FAIL.

- [ ] **Step 3: Implement Control tab**

Add `_render_controls(...)` and include a new tab before raw report.

Controls:

- event path
- config path
- limit
- iterations
- interval
- auto fair confidence
- quick scan button
- bounded collection button
- live safety status

- [ ] **Step 4: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard_app.py tests/test_dashboard.py
git commit -m "feat: add dashboard operator controls"
```

## Task 3: Documentation And Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Make `python -m sports_edge_scanner app` the recommended operator command. Explain paper/shadow collection is configured in the frontend.

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_dashboard.py tests/test_app_launcher.py tests/test_cli.py tests/test_cli_shadow.py tests/test_docs.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 5: Commit docs**

```bash
git add README.md
git commit -m "docs: document single-command app workflow"
```
