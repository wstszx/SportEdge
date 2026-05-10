# Dashboard Operator Controls Design

## Goal

Make `python -m sports_edge_scanner app` the only operator-facing startup command. Paper/shadow collection and future live safety checks should be configured and triggered from the frontend.

## Current Problem

The dashboard displays reports, but it does not start collection jobs. Operators still need to know commands such as `shadow watch`, `shadow scan`, and `shadow report`. That violates the desired workflow: one startup command, then everything through the UI.

## Scope

Included:

- Add a dashboard "Control" tab.
- Let the user configure and run bounded shadow watch from the page.
- Let the user run a quick single-iteration shadow scan from the page.
- Show the resulting readiness summary after the run.
- Show a live-safety panel that makes clear real trading remains disabled.
- Update docs so the recommended startup command is only `python -m sports_edge_scanner app`.

Excluded:

- No long-running background daemon.
- No real live order placement.
- No live order buttons.
- No credential entry in the UI.
- No persistent scheduler.

## UX Behavior

The app starts with:

```bash
python -m sports_edge_scanner app
```

The frontend includes a "Control" tab with:

- Shadow events path
- Shadow config path
- Market limit
- Iterations
- Interval seconds
- Auto fair minimum confidence
- Button: run bounded shadow collection
- Button: run quick one-iteration scan
- Result summary: completed, successful, failed, readiness, blockers
- Live safety message: real orders remain disabled

For the first version, UI-triggered collection is synchronous and bounded. Recommended defaults for UI runs should be short enough not to lock the app for too long:

- quick scan: `iterations=1`, `interval_seconds=0`
- bounded collection: default `iterations=3`, `interval_seconds=0`

Long 20-iteration runs remain possible by changing the form, but the UI should not pretend to be a background scheduler.

## Architecture

Add reusable helpers in `dashboard_app.py`:

- `build_shadow_watch_args(...)`
- `run_dashboard_shadow_watch(...)`

These helpers call existing CLI/core functions instead of duplicating logic:

- `_shadow_watch` from `sports_edge_scanner.cli`
- existing `shadow_events.jsonl`
- existing readiness report

The UI should keep the implementation minimal and auditable. Unit tests can exercise argument construction and helper behavior without launching Streamlit.

## Safety Properties

- The control tab runs only shadow/paper workflows.
- Live panel is read-only safety status.
- Existing live guard remains unchanged.
- UI-triggered shadow watch writes the same event log used by reports.
- Failed collection is surfaced as an error message and, when it happens inside watch, as `shadow_scan_error`.

## Testing

Required tests:

- Dashboard labels include control tab and action labels.
- `build_shadow_watch_args` maps UI values to `_shadow_watch` arguments.
- `run_dashboard_shadow_watch` calls injected runner and returns exit code.
- Dashboard translation covers readiness and scan-error terms.
- README recommends `python -m sports_edge_scanner app` as the operator entry.
- Full test suite remains green.

## Success Criteria

- The user can start the program with one command.
- The user can configure and run paper/shadow collection from the page.
- Readiness remains visible in the page.
- Live trading remains disabled.
