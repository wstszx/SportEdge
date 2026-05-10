# Shadow Reliability Upgrade 2 Design

## Goal

Make the shadow trading system easier to maintain, audit, and run repeatedly by separating the pipeline from the CLI, rebuilding state from event logs, improving reports, adding safe config templates, hardening public-data connectors, and exposing generic outcomes in legacy scan output.

The system remains shadow-only. It must not place real orders, manage wallets, sign payloads, store keys, or control funds.

## Scope

Included:

- Move shadow scan orchestration out of `cli.py` into a focused pipeline module.
- Rebuild shadow state from `shadow_events.jsonl`, including exposure by market/outcome, fills, unfilled notional, and risk rejections.
- Expand `shadow report` so it is useful across multiple runs, not only a single summary count.
- Add `shadow init-config` to generate conservative default config and a fair-probability example file.
- Add retry and response-shape validation to public Polymarket metadata and CLOB orderbook clients.
- Add generic `outcomes` data to legacy `scan --json` output while keeping existing YES/NO fields.

Excluded:

- Dashboard pages for shadow events.
- WebSocket streaming.
- Authenticated CLOB operations.
- Real order placement, cancellation, reconciliation, or private credential handling.

## Architecture

New or changed modules:

- `core.shadow_pipeline`: owns `run_shadow_scan`, order id generation, orderbook age calculation, per-run exposure tracking, event writing, and dependency-injected clients.
- `core.shadow_state`: reads event records and builds replayable shadow state.
- `core.shadow_reports`: uses `shadow_state` to return richer report data.
- `core.shadow_config`: owns default `RiskConfig` serialization and fair-probability example generation.
- `connectors.polymarket`: adds bounded retry and validates the market response is a list-like payload.
- `connectors.polymarket_clob`: adds bounded retry and validates orderbook payload fields.
- `cli`: imports pipeline/config/report helpers and remains a thin command adapter.

Existing files should keep backward compatibility where practical. In particular, existing `scan --json` keys must remain present.

## Pipeline Refactor

The current shadow pipeline lives inside `cli.py`, which makes it harder to test and evolve. Move that logic into `core.shadow_pipeline`.

The public function should remain dependency-injected:

```python
run_shadow_scan(
    market_client,
    book_client,
    fair_book,
    risk_config,
    limit,
    events_path,
    run_id,
    now=None,
) -> dict[str, object]
```

Tests should import it from `core.shadow_pipeline`. `cli.py` may re-export or import it for command handling, but new tests should not depend on CLI internals for pipeline behavior.

## Shadow State

`build_shadow_state(events)` should derive state only from events, with no hidden memory.

State should include:

- accepted order count;
- rejected order count;
- candidate count;
- orderbook error count;
- filled notional;
- unfilled notional;
- average slippage;
- fill status counts;
- rejections by reason;
- exposure by market;
- exposure by market and outcome;
- fill rows suitable for reporting.

Exposure is based on `shadow_fill` events. A full or partial fill increases exposure by `filled_notional`. Unfilled notional is tracked separately and does not increase exposure.

## Report Output

`build_shadow_report(events)` should keep existing top-level keys and add:

- `orderbook_error_count`;
- `simulated_unfilled_notional`;
- `exposure_by_market`;
- `exposure_by_outcome`;
- `risk_decisions`;
- `fills`;
- `data_quality_warnings`.

Warnings should include:

- orderbook errors present;
- rejected orders present;
- unfilled shadow orders present;
- no fills present when candidates existed.

## Config Templates

`shadow init-config` should create two files unless the user overrides paths:

- `shadow_config.json`;
- `fair_probabilities.example.json`.

Defaults must be conservative and match `RiskConfig` defaults.

The command should not overwrite existing files unless `--force` is supplied.

Example:

```bash
python -m sports_edge_scanner shadow init-config
python -m sports_edge_scanner shadow init-config --config my_shadow_config.json --fair fair.example.json --force
```

## Connector Reliability

Add bounded retry to both public connectors:

- default attempts: 2;
- retry delay: 0.25 seconds;
- retry only around network/HTTP/JSON-shape failures;
- preserve clear exceptions after the final attempt.

For Gamma markets:

- accept a list payload directly;
- accept a dict payload containing `markets` or `data`;
- reject any other shape with `ValueError`.

For CLOB orderbooks:

- reject non-object payloads;
- normalize missing bids/asks to empty lists;
- reject orderbooks missing both `asset_id` and the requested token id.

Tests should mock network calls; live API calls remain optional.

## Legacy Scan Outcomes

`market_snapshot(market)` should add:

```json
"outcomes": [
  {"name": "Team A", "price": 0.47, "token_id": "..."}
]
```

Existing keys such as `yes_price`, `no_price`, `yes_break_even`, and `no_break_even` remain for backward compatibility.

Plain-text scan output can remain YES/NO-oriented for now; JSON output must expose generic outcomes so downstream tools can avoid the old assumption.

## Testing

Required tests:

- pipeline behavior imports from `core.shadow_pipeline`;
- CLI parser still exposes `shadow scan`, `shadow report`, and new `shadow init-config`;
- `shadow init-config` writes expected files and refuses overwrite without `--force`;
- `build_shadow_state` reconstructs exposure and unfilled notional from event records;
- `build_shadow_report` includes richer fields and warnings;
- Gamma connector retries once after a transient failure;
- Gamma connector rejects invalid payload shapes;
- CLOB connector retries and validates payload shapes;
- `market_snapshot` includes generic outcomes.

Full suite must pass after implementation.

## Success Criteria

- `cli.py` is thinner and no longer owns the shadow scan pipeline.
- Event logs can be replayed into useful state across multiple runs.
- `shadow report` can explain exposure, fills, rejections, and data quality warnings.
- Users can initialize safe config templates from the CLI.
- Public connector failures are clearer and transient failures are retried.
- Legacy JSON scan consumers keep existing keys while gaining generic outcomes.

