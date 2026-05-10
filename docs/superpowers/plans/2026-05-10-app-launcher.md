# App Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `python -m sports_edge_scanner app` as the normal operator entry point that launches the local dashboard, with optional bounded shadow collection first.

**Architecture:** Add a testable `sports_edge_scanner.core.app_launcher` module for command construction and process execution. Wire it into CLI with an `app` command; keep live mode as a safety message only and reuse existing `shadow watch` behavior for optional paper simulation collection.

**Tech Stack:** Python 3.10+, dataclasses, subprocess command lists, argparse, pytest.

---

## File Structure

- Create `sports_edge_scanner/core/app_launcher.py`: app launch config, Streamlit command builder, launcher.
- Create `tests/test_app_launcher.py`: launcher unit tests.
- Modify `sports_edge_scanner/cli.py`: add `app` command and CLI handler.
- Modify `tests/test_cli.py`: parser and CLI handler tests.
- Modify `README.md`: document `app`.

## Task 1: Core App Launcher

**Files:**
- Create: `sports_edge_scanner/core/app_launcher.py`
- Create: `tests/test_app_launcher.py`

- [ ] **Step 1: Write failing launcher tests**

Tests:

- command includes `python -m streamlit run dashboard_app.py`;
- command includes host, port, and browser flag;
- launcher calls injected process runner and returns its exit code.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_app_launcher.py -q`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement launcher**

Add:

- `AppLaunchConfig`
- `build_streamlit_command(config)`
- `launch_app(config, run_process=subprocess.run)`

- [ ] **Step 4: Run launcher tests**

Run: `python -m pytest tests/test_app_launcher.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/core/app_launcher.py tests/test_app_launcher.py
git commit -m "feat: add app launcher core"
```

## Task 2: CLI App Command

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI parser test**

Test parser supports:

```bash
app --host 127.0.0.1 --port 8502 --no-browser --live
```

- [ ] **Step 2: Run parser test to verify failure**

Run: `python -m pytest tests/test_cli.py::test_parser_supports_app_command -q`

Expected: FAIL.

- [ ] **Step 3: Implement parser and `_app`**

Add `_app(args)` that:

- prints live safety message when `--live`;
- optionally calls `_shadow_watch` when `--shadow-watch`;
- calls `launch_app`.

- [ ] **Step 4: Add and run CLI handler tests**

Use monkeypatch to replace `launch_app` and `_shadow_watch`, proving:

- app launches dashboard;
- `--shadow-watch` runs watch before launch;
- `--live` does not enable real trading.

Run: `python -m pytest tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/cli.py tests/test_cli.py
git commit -m "feat: add app cli command"
```

## Task 3: Documentation And Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update docs**

Document:

```bash
python -m sports_edge_scanner app
python -m sports_edge_scanner app --shadow-watch
python -m sports_edge_scanner app --live
```

Explain `--live` is display/safety context only.

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_app_launcher.py tests/test_cli.py tests/test_cli_shadow.py tests/test_docs.py -q
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
git commit -m "docs: document app launcher"
```
