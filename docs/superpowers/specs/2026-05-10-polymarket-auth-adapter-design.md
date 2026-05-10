# Polymarket Authenticated Adapter Design

## Goal

Design the first authenticated Polymarket execution adapter for the existing venue-neutral `ExecutionClient` interface, without weakening the Live Safety Core. This phase prepares the system for controlled live execution, but implementation must still default to disabled execution and must not bypass legal, geographic, credential, or risk controls.

## Current State

The project now has:

- Public Polymarket/Gamma market discovery.
- Public CLOB orderbook fetching.
- Shadow trading simulation.
- A venue-neutral execution interface.
- `DryRunExecutionClient`.
- `LiveModeGuard`.
- Kill switch, confirmation token, hard notional limits, allowed venues, and append-only audit events.
- `live init-config`, `live check-config`, and `live dry-run`.

The project still has no private-key handling, no signing, no authenticated CLOB client, no real order placement, and no real cancellation.

## Official Documentation Findings

Polymarket's official documentation separates public reads from authenticated trading:

- Public CLOB endpoints such as orderbook/price/spread reads do not require authentication.
- Trading endpoints such as order placement, cancellation, order queries, and heartbeat require authenticated headers.
- Polymarket describes L1 authentication as private-key based.
- Polymarket describes L2 authentication with `POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`, `POLY_API_KEY`, `POLY_PASSPHRASE`, and `POLY_NONCE`.
- Creating orders still requires locally signing the order payload.
- Polymarket provides or references client libraries, including Python, that should be preferred over handwritten signing.
- Polymarket documents geographic restrictions and a geoblock endpoint. Blocked users must not be routed around the restriction.

References:

- <https://docs.polymarket.com/api-reference/authentication>
- <https://docs.polymarket.com/api-reference/geoblock>
- <https://docs.polymarket.com/developers/CLOB/introduction>

## Non-Goals

- Do not hand-roll EIP-712 signing.
- Do not store private keys in repo files.
- Do not accept private keys, API secrets, or passphrases as CLI arguments.
- Do not log secrets, signatures, API keys, passphrases, private keys, or full auth headers.
- Do not bypass Polymarket geographic restrictions.
- Do not add automated real trading loops.
- Do not remove `LiveModeGuard` or make authenticated execution possible without it.
- Do not add WebSocket market making.

## Approach

Use an SDK-first adapter:

1. Add a `PolymarketAuthenticatedExecutionClient` that implements `ExecutionClient`.
2. Delegate signing, authenticated headers, and order submission to the official or official-recommended Python CLOB client.
3. Load credentials only through a dedicated credential provider abstraction.
4. Run a geoblock/readiness check before any authenticated write.
5. Convert venue-neutral `ExecutionOrder` objects into Polymarket order arguments.
6. Normalize Polymarket responses into `ExecutionResult` and `ExecutionOrderStatus`.
7. Keep live execution behind `LiveModeGuard`, kill switch, confirmation token, allowed venue, and hard limits.

This keeps exchange-specific authentication isolated from strategy, risk, CLI, dashboard, and audit logic.

## Components

### `PolymarketCredentials`

A small immutable object for credential material metadata and values:

- `private_key`
- `api_key`
- `api_secret`
- `api_passphrase`
- `funder`
- `signature_type`

Rules:

- `to_dict()` must never include secret values.
- `repr()` must not expose secret values.
- Validation rejects missing required fields.
- Credential objects must not be written into audit events.

### `CredentialProvider`

A protocol with:

- `load() -> PolymarketCredentials`

First implementation:

- `EnvironmentPolymarketCredentialProvider`

Allowed environment variables:

- `POLYMARKET_PRIVATE_KEY`
- `POLYMARKET_API_KEY`
- `POLYMARKET_API_SECRET`
- `POLYMARKET_API_PASSPHRASE`
- `POLYMARKET_FUNDER`
- `POLYMARKET_SIGNATURE_TYPE`

No CLI flags for secrets.

### `PolymarketGeoblockClient`

A small public-read helper:

- `check() -> GeoblockStatus`

`GeoblockStatus`:

- `blocked`
- `country`
- `raw`

If blocked, authenticated execution must return a rejected `ExecutionResult` and emit a sanitized audit event. The adapter must not provide proxy, routing, or bypass behavior.

### `PolymarketOrderMapper`

Converts generic `ExecutionOrder` into SDK order arguments.

Responsibilities:

- Enforce supported sides and order types.
- Map `token_id`, `side`, `limit_price`, `notional`, `time_in_force`.
- Convert notional into order size according to Polymarket SDK expectations.
- Preserve `client_order_id` for audit/idempotency where supported.
- Reject unsupported order types before the SDK is called.

### `PolymarketAuthenticatedExecutionClient`

Implements:

- `place_order(order: ExecutionOrder) -> ExecutionResult`
- `cancel_order(order_id: str) -> ExecutionResult`
- `get_order(order_id: str) -> ExecutionOrderStatus`

Constructor dependencies:

- `credential_provider`
- `sdk_client_factory`
- `geoblock_client`
- `allow_live_writes`

Rules:

- If `allow_live_writes` is false, return rejected results and do not call SDK write methods.
- If geoblock says blocked, return rejected results and do not call SDK write methods.
- If credential loading fails, return a sanitized error result.
- If SDK raises, return a sanitized error result.
- Never include credential values in `raw`, `message`, logs, or events.

### `LiveModeGuard` Integration

The adapter is not a replacement for `LiveModeGuard`. Real execution orchestration must be:

1. Build `ExecutionOrder`.
2. Evaluate strategy/risk.
3. Evaluate `LiveModeGuard`.
4. Only if guard decision is allowed, call `ExecutionClient.place_order`.
5. Emit audit events.

The existing `live mode is not implemented` guard rejection should remain until a separate explicit implementation step changes it.

## Configuration

Add a future `polymarket_auth_config.json` template with non-secret metadata only:

```json
{
  "enabled": false,
  "host": "https://clob.polymarket.com",
  "chain_id": 137,
  "signature_type": 0,
  "funder_env": "POLYMARKET_FUNDER",
  "private_key_env": "POLYMARKET_PRIVATE_KEY",
  "api_key_env": "POLYMARKET_API_KEY",
  "api_secret_env": "POLYMARKET_API_SECRET",
  "api_passphrase_env": "POLYMARKET_API_PASSPHRASE",
  "require_geoblock_check": true,
  "allow_live_writes": false
}
```

The config file names environment variable names only. It must not contain secret values.

## CLI Shape

First CLI additions should be readiness-only:

```bash
python -m sports_edge_scanner polymarket-auth init-config
python -m sports_edge_scanner polymarket-auth check --config polymarket_auth_config.json
python -m sports_edge_scanner polymarket-auth geoblock --json
```

Do not add a CLI command that places a real order in the first implementation of this spec. Real order placement through CLI requires a later explicit spec update.

## Audit Events

Add sanitized audit event types:

- `polymarket_auth_config_check`
- `polymarket_geoblock_check`
- `polymarket_auth_readiness`
- `polymarket_execution_rejected`
- `polymarket_execution_result`
- `polymarket_execution_error`

Event payloads may include:

- status
- reason strings
- venue order id
- client order id
- sanitized SDK status
- geoblock country/block result

Event payloads must not include:

- private key
- API key
- API secret
- API passphrase
- signature
- auth headers
- raw request headers
- raw signed order payload if it can contain signature material

## Error Handling

Normalize errors into safe statuses:

- `credentials_missing`
- `geoblocked`
- `live_writes_disabled`
- `sdk_unavailable`
- `sdk_error`
- `unsupported_order`
- `cancel_rejected`
- `order_not_found`

Raw exception strings must be scrubbed before returning or logging.

## Testing

Required tests:

- Credential provider loads expected env vars.
- Credential provider rejects missing required env vars.
- Credential redaction hides all secret values.
- Config template contains env var names but no secret values.
- Geoblock blocked response prevents SDK write calls.
- `allow_live_writes=false` prevents SDK write calls.
- Order mapper rejects unsupported order types and invalid side.
- Order mapper converts a valid `ExecutionOrder` to SDK arguments.
- Authenticated client normalizes SDK success into `ExecutionResult`.
- Authenticated client normalizes SDK exceptions into sanitized results.
- Cancel and get-order methods normalize fake SDK responses.
- CLI parser supports readiness commands only.
- No new CLI command places real orders.
- Full existing test suite remains green.

All tests must use fake SDK clients and fake credential providers. No real credentials or network writes in tests.

## Security Checklist

- No secret CLI flags.
- No secret defaults.
- No `.env` creation.
- No test fixture containing realistic private keys.
- No raw auth headers in events.
- No raw signed order payloads in events.
- No geoblock bypass.
- No live writes unless both `LiveModeGuard` and adapter write gates allow them.
- No implementation of real order CLI in this phase.

## Success Criteria

- Polymarket-specific auth concerns are isolated behind one adapter boundary.
- Credentials are loaded only through a provider abstraction.
- Adapter behavior is testable with fake SDK clients.
- Readiness checks can validate config shape, credential presence, SDK availability, and geoblock status.
- Real writes remain disabled by default.
- The system is ready for a later, separately approved implementation step that enables tightly controlled live order placement.

## Future Phase

After this adapter exists and is tested, the next design should cover a narrowly scoped real execution workflow:

- operator-initiated one-order live test only;
- explicit config and runtime confirmation;
- tiny maximum notional;
- panic cancel;
- reconciliation after every order;
- no unattended live loop.
