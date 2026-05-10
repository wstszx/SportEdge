# Shadow Ops Upgrade Design

## Goal

Make the shadow trading system easier to operate and review by adding dashboard support for shadow events, a public API smoke command, and a practical runbook.

The project remains shadow-only. This upgrade must not add authenticated trading, private key handling, order placement, order cancellation, or wallet control.

## Scope

Included:

- Add a Shadow tab to the existing Streamlit dashboard.
- Load and report on `shadow_events.jsonl` alongside existing ledger and snapshot files.
- Show shadow exposure, fills, risk rejections, unfilled notional, data quality warnings, and raw shadow report JSON.
- Add `python -m sports_edge_scanner shadow smoke --limit 2` to verify public Gamma and CLOB data access.
- Add a written runbook for initializing config, supplying fair probabilities, running shadow scans, reading reports, and interpreting warnings.

Excluded:

- New frontend framework or separate app.
- Live order placement.
- WebSocket streaming.
- API key, private key, wallet, or auth workflows.
- Automated scheduling or alerting.

## Dashboard Design

The current `dashboard_app.py` remains the only UI entry point.

Add a sidebar input for `shadow_events.jsonl`. The dashboard should read it with existing event-log helpers and build the shadow report through `build_shadow_report`.

Add a Shadow tab with these sections:

- Overview metrics: candidates, accepted orders, rejected orders, filled notional, unfilled notional, average slippage.
- Data quality warnings: render as warnings when present and success when clean.
- Exposure by market: table from `exposure_by_market`.
- Exposure by outcome: table from `exposure_by_outcome`.
- Risk decisions: table from `risk_decisions`.
- Fills: table from `fills`.
- Raw report JSON.

Keep the UI utilitarian and compact. Do not add marketing content or a landing page.

## Smoke Command Design

Add a `shadow smoke` subcommand:

```bash
python -m sports_edge_scanner shadow smoke --limit 2
python -m sports_edge_scanner shadow smoke --limit 2 --json
```

Behavior:

1. Fetch active sports-like markets through `PolymarketClient`.
2. For markets with token ids, attempt to fetch CLOB orderbooks.
3. Report counts for markets found, token orderbooks attempted, successful orderbooks, failures, and warnings.
4. Exit `0` when at least one market is found and every attempted orderbook fetch succeeds.
5. Exit `1` when public data cannot be fetched or all orderbook attempts fail.

This command must never use credentials or place orders.

## Runbook

Create `docs/shadow_trading_runbook.md`.

It should cover:

- Research-only safety boundary.
- `shadow init-config`.
- Fair probability file shape.
- Running `shadow smoke`.
- Running `shadow scan`.
- Running `shadow report`.
- Opening the dashboard.
- What each warning means.
- Conditions where results should not be trusted, such as stale orderbooks, missing fills, orderbook errors, and insufficient fair-probability evidence.

## Testing

Required tests:

- Dashboard data helpers convert shadow report dictionaries into table rows.
- Dashboard state includes shadow report data when shadow events are supplied.
- CLI parser supports `shadow smoke`.
- Smoke command can be tested with fake market and book clients.
- Smoke command returns non-zero when no markets or no orderbooks can be fetched.
- Runbook file exists and contains the key commands.

Network-dependent live smoke tests remain manual and are not part of the normal test suite.

## Success Criteria

- The dashboard can load `shadow_events.jsonl` and display operationally useful shadow state.
- `shadow smoke` provides a quick public-data health check without credentials.
- The runbook gives a user enough guidance to operate shadow mode safely.
- Existing tests still pass.

