# Shadow Readiness Gate Design

## Goal

Add an automatic readiness gate to shadow trading reports so the program can decide whether paper simulation has enough clean evidence to proceed toward a later stage. The operator should not need to manually interpret raw counters.

## Current Problem

Shadow mode can now run without a manual fair-probability file and can report model estimates, candidates, fills, rejections, and warnings. However, the report still leaves the main operational question to the user:

- Is this paper run trustworthy enough?
- What exact evidence is missing?
- Which issues block the next stage?

That is not acceptable for a reliable practical trading system. The program should produce an explicit readiness verdict with blockers and thresholds.

## Scope

Included:

- Add a conservative readiness evaluator for shadow reports.
- Add configurable thresholds with safe defaults.
- Include readiness output in `shadow report` JSON and text output.
- Count distinct shadow runs from event `run_id` values.
- Keep the gate fully local and deterministic.

Excluded:

- No real trading enablement.
- No automatic live-mode config changes.
- No performance claims from public market-implied probabilities.
- No ML, paid data provider, or strategy optimization.
- No hidden override that can mark a weak run ready.

## Readiness Output

`shadow report` should include:

- `readiness.ready`: boolean
- `readiness.blockers`: list of blocking reasons
- `readiness.warnings`: list of non-blocking concerns
- `readiness.metrics`: observed values used by the gate
- `readiness.thresholds`: configured threshold values

Text output should print the readiness verdict and blockers after the existing summary.

## Default Thresholds

Create `ShadowReadinessConfig` with conservative defaults:

- `min_run_count`: `20`
- `min_model_estimate_count`: `200`
- `min_usable_estimate_rate`: `0.5`
- `min_fill_count`: `20`
- `max_orderbook_error_count`: `0`
- `max_rejected_order_count`: `0`
- `max_unfilled_notional`: `0.0`
- `max_average_slippage`: `0.02`

These defaults are intentionally strict. Early paper runs should normally be `ready: false`; that is useful feedback, not failure.

## Readiness Rules

The gate returns `ready: false` if any blocker exists:

- `run_count` is below `min_run_count`.
- `model_estimate_count` is below `min_model_estimate_count`.
- `usable_model_estimate_count / model_estimate_count` is below `min_usable_estimate_rate`.
- Number of fills is below `min_fill_count`.
- `orderbook_error_count` exceeds `max_orderbook_error_count`.
- `rejected_order_count` exceeds `max_rejected_order_count`.
- `simulated_unfilled_notional` exceeds `max_unfilled_notional`.
- `average_slippage` exceeds `max_average_slippage` when fills exist.

The gate should add warnings from existing `data_quality_warnings` so the readiness section mirrors the rest of the report.

## Components

### `sports_edge_scanner.core.shadow_readiness`

New module:

- `ShadowReadinessConfig`
- `evaluate_shadow_readiness(report, config=None)`

The evaluator accepts a shadow report dictionary and returns a JSON-serializable readiness dictionary.

### `sports_edge_scanner.core.shadow_state`

Extend state replay with:

- `run_count`
- `run_ids`

`run_count` should count distinct non-empty `run_id` values. If old/manual event lists contain events but no `run_id`, `run_count` can remain `0`; the readiness gate will correctly block with insufficient run evidence.

### `sports_edge_scanner.core.shadow_reports`

After building state and data-quality warnings:

1. Build the report dictionary.
2. Evaluate readiness with default thresholds.
3. Attach `readiness`.

### CLI

Update `shadow report` text output to print:

- readiness status
- blockers, if any

JSON output already includes the full report, so it will include readiness automatically.

## Safety Properties

- The gate cannot enable real orders.
- The default verdict is conservative.
- Insufficient sample size is a blocker.
- Data-quality problems are explicit blockers or warnings.
- A clean readiness verdict still means "paper evidence is adequate for the next design review", not "live trading is safe".

## Testing

Required tests:

- Empty report is not ready and lists missing run/model/fill evidence.
- Clean report can be ready when thresholds are satisfied.
- Low usable-estimate rate blocks readiness.
- Orderbook errors, rejected orders, unfilled notional, and high slippage block readiness.
- `build_shadow_state` counts distinct run ids.
- `build_shadow_report` includes a `readiness` section.
- CLI text report prints readiness status.
- Full test suite remains green.

## Success Criteria

- A user can run `shadow report` and see a direct readiness verdict.
- The verdict includes exact blockers and thresholds.
- The program no longer expects the user to infer readiness from raw counters.
- No live-trading behavior changes.
