# Live Safety Core Design

## Goal

Build the first production-safety layer for a future live trading system: a venue-neutral execution interface, explicit live-mode guardrails, audit logging, and hard risk controls. This phase must not place real orders, cancel real orders, sign payloads, load private keys, or manage wallets.

## Current State

Sports Edge Scanner is currently research/shadow-only:

- Public Polymarket/Gamma market data and CLOB orderbook data are fetched without credentials.
- Shadow mode converts candidates into simulated orders and fills.
- Risk controls already evaluate edge, liquidity, spread, stale orderbooks, slippage, daily loss, and exposure limits.
- Event logs and the dashboard can report shadow candidates, risk decisions, fills, warnings, and exposure.
- The README and runbook explicitly say the project does not place real bets or control funds.

That is a good base, but it is not a live trading system yet. Reliable live trading requires a safety layer that is independent of any one exchange adapter.

## External Reference

Polymarket's official CLOB documentation currently distinguishes public read endpoints from authenticated trading endpoints:

- Public market/orderbook/price/spread reads do not require authentication.
- Trading endpoints such as placing orders, cancellations, and heartbeat require authenticated headers.
- The CLOB uses L1 private-key authentication and L2 API-key authentication.
- Even with L2 authentication headers, creating orders still requires signing the order payload.
- Polymarket recommends secure key storage and says private keys must never be committed.

Reference: <https://docs.polymarket.com/api-reference/authentication>

This design deliberately keeps all private-key, signing, and authenticated trading work out of the first implementation phase.

## Non-Goals

- No real order placement.
- No real order cancellation.
- No private-key, wallet, or API-secret loading.
- No Polymarket authenticated client implementation.
- No automated scheduling or daemon process.
- No cloud deployment.
- No strategy changes.

## Approach

Use a venue-neutral execution core with safe default implementations:

1. Represent live-ready order intent separately from shadow orders.
2. Evaluate every order intent through a `LiveModeGuard`.
3. Send approved intents only to an injected `ExecutionClient`.
4. Start with a `DryRunExecutionClient` that records what would be sent but never calls a trading venue.
5. Emit append-only audit events for every decision, rejection, guard check, and dry-run execution.

Polymarket can later become an `ExecutionClient` adapter, but it will have to pass through the same guard, risk, and audit layer.

## Components

### `ExecutionClient`

A small protocol for venue adapters:

- `place_order(order: ExecutionOrder) -> ExecutionResult`
- `cancel_order(order_id: str) -> ExecutionResult`
- `get_order(order_id: str) -> ExecutionOrderStatus`

The interface is intentionally generic. It should not mention Polymarket, CLOB, wallets, or signing.

### `DryRunExecutionClient`

The first implementation of `ExecutionClient`.

Behavior:

- Accepts validated execution orders.
- Returns deterministic dry-run order ids.
- Emits results with status `dry_run_accepted`.
- Never performs network requests to trading endpoints.
- Never accepts credentials.

### `ExecutionOrder`

A venue-neutral live-order intent:

- `client_order_id`
- `market_id`
- `market_slug`
- `outcome_name`
- `token_id`
- `side`
- `order_type`
- `limit_price`
- `notional`
- `time_in_force`
- `source_signal_id`
- `created_at`

Validation rules:

- `side` must be `BUY` or `SELL`.
- `order_type` starts with `LIMIT` only.
- `limit_price` must be greater than `0` and less than `1`.
- `notional` must be positive.
- `token_id`, `market_id`, and `client_order_id` must be present.

### `ExecutionResult`

The result returned by an execution client:

- `client_order_id`
- `venue_order_id`
- `status`
- `filled_notional`
- `remaining_notional`
- `average_price`
- `message`
- `raw`

For the first phase, dry-run results are enough.

### `LiveModeConfig`

Configuration for the live safety layer:

- `mode`: `dry_run` or `live`
- `live_enabled`: default `false`
- `require_confirmation_token`: default `true`
- `confirmation_token`: optional string that must match the requested runtime token
- `kill_switch_enabled`: default `true`
- `max_order_notional`
- `max_market_exposure`
- `max_total_exposure`
- `daily_loss_limit`
- `allowed_venues`

In this phase, `live` mode is rejected because no authenticated execution adapter exists yet.

### `LiveModeGuard`

A gate that must approve every execution request.

Reject when:

- `kill_switch_enabled` is true.
- Config mode is unknown.
- Config mode is `live` but `live_enabled` is false.
- Config mode is `live` in this phase.
- Confirmation token is required and missing/mismatched.
- Requested order exceeds configured hard limits.
- Venue is not in `allowed_venues`.
- Risk decision is not explicitly allowed.

Return a structured `GuardDecision`:

- `allowed`
- `reasons`
- `mode`
- `requested_notional`
- `approved_notional`

### Audit Events

Append JSONL events through the existing event helper:

- `execution_intent`
- `live_guard_decision`
- `execution_rejected`
- `execution_dry_run`
- `execution_result`
- `execution_error`

Audit events must not include secrets. Future credential-bearing adapters must redact all auth material before event emission.

## Data Flow

1. Existing signal/shadow logic identifies a candidate.
2. Candidate becomes an `ExecutionOrder`.
3. Existing risk controls produce a `RiskDecision`.
4. `LiveModeGuard` evaluates config, kill switch, confirmation, venue, risk, and hard limits.
5. Rejected orders emit `live_guard_decision` and `execution_rejected`.
6. Approved dry-run orders go to `DryRunExecutionClient`.
7. Result emits `execution_dry_run` and `execution_result`.
8. Reports and dashboard can later summarize execution audit events.

## CLI Shape

Add a future `live` command group, but keep it dry-run only:

```bash
python -m sports_edge_scanner live init-config
python -m sports_edge_scanner live check-config --config live_config.json
python -m sports_edge_scanner live dry-run --limit 20 --fair fair_probabilities.json --risk shadow_config.json --live-config live_config.json --events execution_events.jsonl
```

The first implementation should not provide `live trade` or any command name that implies real order placement.

## Safety Rules

- Default config must not permit live trading.
- Missing config means safe rejection, not permissive defaults.
- Dry-run execution must not use authenticated clients.
- No secret values may be accepted as CLI flags.
- No secret values may be written to logs, JSONL events, reports, or dashboard state.
- A kill switch defaults to enabled and must be explicitly disabled for dry-run execution.
- A later real adapter must require a separate design and implementation plan.

## Testing

Required tests for this phase:

- Execution order validation rejects missing ids, invalid side, invalid price, and non-positive notional.
- `DryRunExecutionClient` returns deterministic dry-run results without network calls.
- `LiveModeGuard` rejects when kill switch is enabled.
- `LiveModeGuard` rejects `live` mode in this phase.
- `LiveModeGuard` rejects missing confirmation token when required.
- `LiveModeGuard` rejects disallowed venue and disallowed risk decision.
- `LiveModeGuard` approves valid dry-run execution when kill switch is disabled and token matches.
- CLI parser supports `live init-config`, `live check-config`, and `live dry-run`.
- Config template defaults to safe rejection.
- Audit events are written for intent, guard decision, dry-run result, and rejection.
- Full existing test suite remains green.

## Success Criteria

- The project has a venue-neutral execution interface.
- The only executable adapter is dry-run.
- No private keys, API secrets, signing code, or live trading endpoints are added.
- Every execution attempt produces append-only audit events.
- Live mode is structurally present but intentionally blocked.
- Future Polymarket live execution can be added behind the same interface and guard layer.

## Future Phases

### Phase 2: Polymarket Authenticated Adapter Design

Add a separate spec for authenticated Polymarket CLOB trading, including credential loading, signing, L1/L2 authentication, funder/signature type configuration, order placement, cancellation, heartbeat, and reconciliation.

### Phase 3: Production Operations

Add reconciliation, open-order polling, position checks, panic cancel, operator health checks, alerting, and deployment runbooks.
