# App Launcher Design

## Goal

Add a single operator-facing command that starts the local frontend page for both paper/shadow workflows and future live-readiness workflows. The user should not need to remember `streamlit run dashboard_app.py`.

## Current Problem

The project already has a Streamlit dashboard, but it is launched separately from the CLI. For a practical trading program, the normal operator experience should begin with a local control/monitoring page, not a collection of disconnected commands.

## Scope

Included:

- Add `python -m sports_edge_scanner app`.
- Launch the existing Streamlit dashboard from the CLI.
- Add options for host, port, and browser behavior.
- Add optional `--shadow-watch` mode to run bounded shadow collection alongside the dashboard.
- Add `--live` mode as a safe UI context flag only; it must not enable live execution.
- Keep the launch logic testable without starting real Streamlit in unit tests.

Excluded:

- No real trading buttons.
- No live order execution from the frontend.
- No process supervisor or background service.
- No authentication system.
- No frontend rewrite.

## CLI Behavior

Default:

```bash
python -m sports_edge_scanner app
```

Starts:

```bash
python -m streamlit run dashboard_app.py
```

Default dashboard data files:

- `paper_trades.jsonl`
- `market_snapshots.jsonl`
- `shadow_events.jsonl`

Options:

- `--host`: default `localhost`
- `--port`: default `8501`
- `--no-browser`: do not auto-open browser
- `--shadow-watch`: start bounded shadow watch before/alongside dashboard
- `--watch-limit`: default `20`
- `--watch-iterations`: default `20`
- `--watch-interval-seconds`: default `1800.0`
- `--shadow-config`: default `shadow_config.json`
- `--shadow-events`: default `shadow_events.jsonl`
- `--live`: launch dashboard in live-readiness context only; print a safety message that real live execution is still disabled.

## Architecture

Create `sports_edge_scanner.core.app_launcher`:

- `AppLaunchConfig`
- `build_streamlit_command(config)`
- `launch_app(config, run_process=subprocess.run)`

`launch_app` should:

1. Optionally run shadow watch when `shadow_watch` is enabled.
2. Build a Streamlit command.
3. Start Streamlit through the injected process runner.

The CLI `_app` function will translate parsed arguments into `AppLaunchConfig`.

## Shadow Watch Integration

For first implementation, `--shadow-watch` may run bounded collection before starting the dashboard. This avoids process management complexity while still giving the operator one command:

```bash
python -m sports_edge_scanner app --shadow-watch --watch-iterations 20
```

After watch finishes, the dashboard starts and displays the generated event log. A later version can run watch and dashboard concurrently with a supervisor.

## Safety Properties

- `app` starts a local UI only.
- `--live` never disables kill switches.
- `--live` never places orders.
- `--shadow-watch` remains shadow-only and uses existing paper simulation.
- Unit tests do not start real Streamlit.

## Testing

Required tests:

- Parser supports `app`.
- Streamlit command includes dashboard path, host, port, and browser flag.
- `launch_app` calls injected process runner instead of starting a real process.
- `app --live` prints safe live-readiness message.
- `app --shadow-watch` calls the existing shadow watch path before launching dashboard.
- Full test suite remains green.

## Success Criteria

- A user can run one command to open the frontend page.
- The same command can optionally collect shadow evidence first.
- No live trading behavior is enabled.
- Existing dashboard behavior remains unchanged.
