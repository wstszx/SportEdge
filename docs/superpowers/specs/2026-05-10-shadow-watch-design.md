# Shadow Watch Design

## Goal

Add a bounded shadow watch command that automatically runs repeated shadow scans, appends all events to one log, records scan failures, and prints a final readiness report. The operator should not need to manually run `shadow scan` many times to accumulate evidence.

## Current Problem

The system can run one shadow scan and can judge readiness from accumulated event logs. However, the user still has to manually repeat scans. A reliable paper-simulation workflow should:

- run repeated scans on a schedule;
- create a distinct `run_id` for each iteration;
- keep writing to the same append-only event log;
- record data-source or scan failures as events;
- show the final readiness verdict automatically.

## Scope

Included:

- Add a bounded `shadow watch` CLI command.
- Add a testable core watch loop.
- Validate iteration and interval inputs.
- Sleep between iterations, but never after the last iteration.
- Continue after individual scan failures.
- Append `shadow_scan_error` events for failed iterations.
- Add failure counts to shadow reports and readiness.
- Print final readiness after the watch loop.

Excluded:

- No infinite daemon mode.
- No background scheduler or OS service.
- No live order placement.
- No automatic config edits.
- No external notification system.

## CLI Behavior

New command:

```bash
python -m sports_edge_scanner shadow watch --limit 20 --iterations 20 --interval-seconds 1800 --events shadow_events.jsonl
```

Options:

- `--limit`: markets per scan, default `20`
- `--iterations`: number of bounded scan iterations, default `20`
- `--interval-seconds`: delay between iterations, default `1800.0`
- `--events`: event log path, default `shadow_events.jsonl`
- `--config`: shadow risk config path, optional
- `--fair`: optional manual fair-probability override
- `--auto-fair-min-confidence`: default `0.75`
- `--json`: print machine-readable summary

Text output should include:

- completed iterations
- successful iterations
- failed iterations
- event path
- final readiness verdict
- readiness blockers, if any

## Core API

Create `sports_edge_scanner.core.shadow_watch`:

```python
def run_shadow_watch(
    scan_once,
    build_report,
    events_path: Path,
    iterations: int,
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    ...
```

`scan_once(iteration_index)` should run one scan and return a scan summary. The watch loop is responsible for validation, failure handling, sleeping, and final reporting.

The CLI will provide a `scan_once` closure that:

- creates a new `run_id`;
- calls `run_shadow_scan`;
- passes the same event path for every scan.

## Failure Events

When a scan iteration raises, append:

```json
{
  "event_type": "shadow_scan_error",
  "run_id": "...",
  "iteration": 1,
  "error": "..."
}
```

Then continue to the next iteration. The final summary should show failed iterations.

## Reporting And Readiness

Extend shadow state/report with:

- `shadow_scan_error_count`

Extend readiness so any `shadow_scan_error_count > 0` is a blocker:

- `shadow scan errors present`

This prevents a watch run with hidden data-source failures from looking ready.

## Safety Properties

- Watch mode remains paper/shadow only.
- The loop is bounded by `--iterations`.
- Failed scans are auditable events.
- The final readiness gate remains conservative.
- The command does not modify live trading config or credentials.

## Testing

Required tests:

- Watch loop runs requested iterations and sleeps only between iterations.
- Watch loop rejects invalid iterations and intervals.
- Watch loop continues after scan failure and writes `shadow_scan_error`.
- Shadow report counts `shadow_scan_error` events.
- Readiness blocks when scan errors are present.
- CLI parser supports `shadow watch`.
- CLI watch text output prints final readiness.
- Full test suite remains green.

## Success Criteria

- A user can run one bounded command to accumulate paper simulation evidence.
- Each iteration has a distinct `run_id`.
- Failures are visible in the event log and readiness blockers.
- The final output tells the user whether the accumulated evidence is ready for the next review stage.
