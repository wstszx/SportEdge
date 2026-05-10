# Strategy Diagnostics Design

## Goal

Explain why shadow mode is not producing simulated fills without weakening safety gates. The system should tell the operator whether the blocker is sample size, model quality, candidate generation, execution quality, or missing independent signal.

## Current Problem

Readiness currently reports blockers such as `insufficient fills`, but that does not explain why fills are missing. In the current conservative auto-fair model, fair probabilities are near executable market prices, so candidate signals are usually absent. That is safe, but the operator needs a clear next action.

## Scope

Included:

- Add a deterministic strategy diagnostics evaluator.
- Attach diagnostics to shadow reports.
- Show diagnostics in the dashboard Shadow and Control tabs.
- Produce clear next actions without changing trading thresholds.

Excluded:

- No lower edge thresholds.
- No fake candidates.
- No live trading enablement.
- No sportsbook/data-provider integration yet.
- No ML model.

## Diagnostic Output

`shadow_report["strategy_diagnostics"]` should include:

- `status`: `collecting_data`, `needs_independent_signal`, `needs_execution_samples`, `execution_quality_issue`, or `healthy`
- `issues`: list of current problems
- `next_actions`: list of recommended actions
- `metrics`: candidate count, fill count, run count, model estimate count, usable estimate rate, rejection/error counts

## Rules

- If run count or model estimate count is below readiness thresholds, status is `collecting_data`.
- If model estimate count is adequate, usable rate is adequate, but candidate count is zero, status is `needs_independent_signal`.
- If candidates exist but fills are zero, status is `needs_execution_samples`.
- If rejected orders, orderbook errors, scan errors, unfilled notional, or high slippage are present, status is `execution_quality_issue`.
- If readiness is ready and no issues remain, status is `healthy`.

The evaluator should reuse `ShadowReadinessConfig` defaults so diagnostics and readiness agree about thresholds.

## Dashboard Behavior

The Shadow tab should display:

- diagnostics status;
- issues;
- next actions.

The Control tab should show the same diagnostics near readiness so the user sees what to do next after running collection.

## Safety Properties

- Diagnostics never create orders.
- Diagnostics never reduce risk thresholds.
- Diagnostics explicitly recommend independent signal integration when no candidates are produced by the conservative baseline.
- Readiness remains the gate.

## Testing

Required tests:

- Collecting-data status when run/model samples are insufficient.
- Needs-independent-signal status when estimates are adequate but candidates are zero.
- Needs-execution-samples status when candidates exist but fills are zero.
- Execution-quality issue status when errors or rejections exist.
- Healthy status when readiness is true.
- Shadow report includes diagnostics.
- Dashboard labels and translations include diagnostics.
- Full test suite remains green.

## Success Criteria

- The frontend no longer leaves the user stuck at "insufficient fills" without explanation.
- The report explains why fills are absent.
- The next action is explicit and conservative.
