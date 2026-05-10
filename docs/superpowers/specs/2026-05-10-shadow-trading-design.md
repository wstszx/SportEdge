# Shadow Trading Reliability Upgrade Design

## Goal

Upgrade Sports Edge Scanner from a research-only market scanner into a reliable shadow trading system that can rehearse live-trading behavior without sending real orders, handling private keys, or controlling user funds.

The system should answer a practical question: "If this strategy were allowed to trade right now, what orders would it attempt, which orders would risk controls reject, what fills would the orderbook imply, and how would the simulated position perform over time?"

## Scope

This phase builds a quasi-live shadow execution pipeline. It does not place real orders, sign payloads, manage wallets, store private keys, bypass geographic restrictions, or guarantee profitability.

Included:

- Generic outcome and token handling for binary markets that are not named YES and NO.
- Public Polymarket market discovery through Gamma metadata.
- Public Polymarket CLOB orderbook reads for token-level bid and ask depth.
- Risk checks before every shadow order.
- A shadow execution engine that simulates limit-order fills against observed orderbook liquidity.
- Append-only JSONL event logs for snapshots, signals, risk decisions, shadow orders, and shadow fills.
- Reports that summarize simulated fill quality, rejection reasons, exposure, PnL, and data quality.

Excluded:

- Authenticated Polymarket CLOB trading endpoints.
- API key, private key, wallet, or allowance handling.
- Real order placement, cancellation, heartbeat, user-channel reconciliation, or settlement automation.
- Strategy model development beyond accepting user-supplied fair probabilities.
- Legal, tax, or jurisdiction advice.

## External API Assumptions

The design relies only on public data endpoints in this phase.

- Polymarket Gamma market metadata remains the source for market discovery, titles, outcomes, condition ids, token ids, and activity flags.
- Polymarket CLOB orderbook reads are public and do not require authentication.
- Polymarket market WebSocket data is public, but the first implementation may use REST snapshots before adding streaming.
- Authenticated order placement requires L1/L2 authentication and signed orders, so it stays out of scope until a later real-trading phase.

If an API response shape changes, the connector should fail closed with a clear warning and produce no candidate order rather than silently trading on incomplete data.

## Architecture

The upgrade keeps the current package layout and adds small, focused modules.

- `connectors.polymarket` continues to normalize Gamma market metadata.
- `connectors.polymarket_clob` reads public token orderbooks from the CLOB API.
- `models` grows generic outcome, orderbook, risk, shadow order, and shadow fill dataclasses.
- `core.pricing` remains pure probability and price math.
- `core.signals` stops assuming YES and NO and can classify any supported binary outcome pair.
- `core.risk` evaluates whether a candidate shadow order is allowed.
- `core.shadow_execution` simulates fills against orderbook levels.
- `core.events` writes and reads append-only JSONL event records.
- `core.shadow_reports` builds reports from shadow events.
- `cli` adds `shadow scan` and `shadow report` commands while preserving existing research commands.

Each module must be testable without network access. Network clients should be thin adapters around pure models.

## Data Model

The current `MarketOutcome` already has `name`, `price`, and `token_id`. The shadow phase treats `token_id` as required for orderbook-backed execution. Markets without token ids can still appear in research output but cannot produce shadow orders.

New model concepts:

- `OrderBookLevel`: price and size at one bid or ask level.
- `OrderBook`: token id, market id, bids, asks, timestamp, and optional tick size.
- `CandidateOrder`: market id, outcome name, token id, side, limit price, intended size, fair probability, edge, and reason.
- `RiskDecision`: allowed flag plus rule-specific reasons and adjusted size when applicable.
- `ShadowOrder`: accepted order intent after risk checks, including limit price, size, time-in-force, and source signal id.
- `ShadowFill`: simulated fill details, including average price, filled size, unfilled size, slippage, and matched book levels.
- `ShadowPosition`: aggregate simulated exposure by market and outcome.

Prices remain decimal probabilities between 0 and 1. Sizes represent notional dollars unless a field explicitly says contracts.

## Market And Outcome Handling

The scanner must stop treating YES and NO as the only valid outcome names.

For a binary market:

- If outcomes are `YES` and `NO`, retain the existing labels.
- If outcomes are team names or other binary labels, preserve those labels and use their token ids.
- The user can provide fair probabilities by outcome name, token id, market slug, or market id.
- Snapshot and report output should include generic outcome rows rather than only `yes_price` and `no_price`.

Legacy `yes_price` and `no_price` fields may remain for backward compatibility, but shadow trading logic must use generic outcome collections.

## Signal Generation

Signals remain conservative. A candidate order can be produced only when all of these are true:

- The market is active and not closed.
- The selected outcome has a valid token id.
- A fair probability is supplied for that specific outcome.
- The orderbook has a valid best ask for a buy-side candidate.
- The fair probability exceeds the executable ask price plus configured minimum edge and cost buffer.
- Liquidity at or below the limit price can satisfy a minimum fill threshold.

The first shadow phase only models buy-side limit orders for outcome tokens. Sell-side and short/redeem logic can be added after position tracking has proven reliable.

## Risk Controls

Risk checks must run after signal generation and before shadow execution. A rejected candidate must be logged with reasons.

Required rules:

- `max_order_notional`: reject or reduce any single order above this notional.
- `max_market_exposure`: reject or reduce orders that would exceed exposure in one market.
- `max_total_exposure`: reject or reduce orders that would exceed total simulated exposure.
- `min_liquidity`: reject markets below configured liquidity.
- `max_spread`: reject orderbooks with too wide a best bid/ask spread.
- `max_slippage`: reject fills whose simulated average price exceeds the limit or slippage cap.
- `min_edge`: reject weak candidates after executable-price checks.
- `daily_loss_limit`: stop new orders when simulated realized plus marked PnL crosses the configured loss limit.
- `stale_book_seconds`: reject orderbooks older than the configured freshness window.

Defaults should be intentionally small and conservative. The CLI must expose a config file path so users do not encode risk settings into command history.

## Shadow Execution

The execution engine simulates a buy limit order by walking ask levels from best to worst until one of these occurs:

- The requested notional is fully filled.
- The next ask is above the limit price.
- The book runs out of eligible ask liquidity.

The engine records:

- requested notional;
- filled notional;
- filled contracts;
- average execution price;
- unfilled notional;
- slippage versus best ask and versus requested limit;
- book levels consumed;
- whether the order was full, partial, or unfilled.

No fill should be simulated from prices above the limit. Partial fills are valid and must be visible in reports.

## Event Log

The shadow system uses append-only JSONL so runs can be audited and replayed.

Default files:

- `market_snapshots.jsonl` for legacy snapshots.
- `shadow_events.jsonl` for new shadow pipeline events.

Event types:

- `market_snapshot`: normalized market metadata and outcome prices.
- `orderbook_snapshot`: token-level bid and ask levels.
- `signal`: candidate or watch decision.
- `risk_decision`: allowed or rejected decision with reasons.
- `shadow_order`: post-risk simulated order intent.
- `shadow_fill`: simulated execution result.
- `shadow_mark`: later mark-to-market value for open shadow positions.

Every event must include:

- `event_type`;
- `timestamp`;
- `run_id`;
- `market_id` when available;
- `source`;
- schema version.

The writer should flush each record immediately enough that an interrupted run leaves useful data.

## CLI

Existing commands stay compatible.

New commands:

```bash
python -m sports_edge_scanner shadow scan --limit 20 --fair fair_probabilities.json --config shadow_config.json
python -m sports_edge_scanner shadow report --events shadow_events.jsonl
```

`shadow scan` should:

1. Fetch candidate markets.
2. Normalize outcomes and token ids.
3. Load fair probabilities and risk config.
4. Fetch public orderbooks for outcomes with supplied probabilities.
5. Generate candidate orders.
6. Run risk checks.
7. Simulate shadow fills for accepted orders.
8. Append all events.
9. Print a compact summary and optionally JSON.

`shadow report` should summarize:

- candidate count;
- accepted order count;
- rejected order count by reason;
- full, partial, and unfilled order counts;
- simulated notional filled;
- average slippage;
- open exposure by market;
- mark-to-market PnL when marks are available;
- data quality warnings.

## Configuration

The default config should be safe enough for first runs:

```json
{
  "max_order_notional": 10.0,
  "max_market_exposure": 25.0,
  "max_total_exposure": 100.0,
  "min_liquidity": 1000.0,
  "max_spread": 0.08,
  "max_slippage": 0.02,
  "min_edge": 0.03,
  "daily_loss_limit": 25.0,
  "stale_book_seconds": 30
}
```

Fair probability file example:

```json
{
  "markets": {
    "market-slug-or-id": {
      "YES": 0.55,
      "Team A": 0.57
    }
  },
  "tokens": {
    "1234567890": 0.57
  }
}
```

Token-specific probabilities override market/outcome probabilities.

## Error Handling

The system must fail closed:

- Missing token id means no shadow order.
- Missing orderbook means no shadow order.
- Empty asks mean no buy-side shadow order.
- Invalid fair probability rejects the input before scanning.
- Network failure produces a clear run-level warning and non-zero exit for CLI commands that cannot complete.
- Per-market connector failures should be logged and should not abort unrelated markets unless all markets fail.

Errors should not be swallowed into watch-only output when they affect order simulation.

## Testing

Tests should prioritize pure behavior:

- Generic outcome lookup and fair probability matching.
- Signal generation for non-YES/NO outcomes.
- Orderbook normalization.
- Risk accept, reject, and size-reduction paths.
- Shadow fill simulation for full, partial, unfilled, and price-capped orders.
- Event JSONL append/read behavior.
- Shadow report aggregation.
- CLI argument parsing and mocked end-to-end shadow scan.

Network tests must mock HTTP responses. Live network smoke tests are optional and should not be required for the normal suite.

## Rollout Plan

Phase 1 creates a working REST-backed shadow scanner with conservative defaults and tests.

Phase 2 can add WebSocket orderbook streaming once the REST-backed flow is stable.

Phase 3 can add authenticated user-channel reconciliation and real-order abstractions, still without enabling actual order placement by default.

Phase 4 can consider small-size real trading only after shadow reports show stable data quality, clear risk behavior, and repeatable reconciliation.

## Success Criteria

The phase is successful when:

- The original test suite still passes.
- The scanner can shadow-scan markets with arbitrary binary outcome labels.
- No real trading credentials are required anywhere.
- Every candidate is either rejected with an explicit risk reason or produces a deterministic shadow fill result.
- A user can inspect `shadow_events.jsonl` and reconstruct why each simulated order happened.
- `shadow report` exposes enough quality metrics to decide whether a strategy deserves further paper testing.

