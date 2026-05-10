# Auto Fair Probability Engine Design

## Goal

Remove the requirement for the operator to hand-edit `fair_probabilities.json` before running paper/shadow simulation. The program should generate conservative fair-probability estimates from available market data, attach confidence and reasons, and refuse to create candidate trades when the estimate is not reliable enough.

## Current Problem

The current shadow pipeline requires a `FairProbabilityBook`. If the user does not supply fair probabilities, signals stay in watch mode with `no fair probability supplied`.

That is acceptable for a research notebook, but it is not acceptable for a reliable trading program. A reliable system should:

- produce its own model input;
- explain the source of that input;
- quantify confidence;
- refuse to trade when the model is weak;
- avoid asking the operator to edit JSON files for normal use.

## Scope

Included:

- Add an automatic fair-probability estimator.
- Add confidence scoring and reason strings.
- Convert reliable estimates into a `FairProbabilityBook`.
- Let `shadow scan` use automatic probabilities when `--fair` is omitted.
- Emit audit events for model estimates.
- Report when estimates are too weak to trade.

Excluded:

- No sports team/player statistical model yet.
- No paid data provider integration.
- No machine learning training pipeline.
- No claims that market-implied probability is predictive edge.
- No real trading changes.

## Approach

Implement a conservative baseline model:

1. Use public market and CLOB orderbook data only.
2. Estimate each outcome's baseline probability from executable midpoint data:
   - prefer orderbook bid/ask midpoint when both sides exist;
   - fall back to displayed outcome price when orderbook midpoint is unavailable.
3. Score confidence from observable data quality:
   - tighter spread increases confidence;
   - higher liquidity increases confidence;
   - deeper top-of-book size increases confidence;
   - active/open market increases confidence;
   - missing orderbook, missing price, low liquidity, wide spread, or closed market reduce confidence.
4. Only publish a fair probability when confidence is above a configured threshold.
5. Published probabilities are deliberately conservative: they should not create edge merely because the model copied the market. In the first version, the estimate should be close to the current executable price, so most markets should not generate trades unless later model sources add independent evidence.

This makes the flow automatic while avoiding fake confidence.

## Components

### `FairProbabilityEstimate`

New dataclass:

- `market_id`
- `market_slug`
- `outcome_name`
- `token_id`
- `probability`
- `confidence`
- `source`
- `reasons`
- `usable`

### `AutoFairConfig`

New dataclass:

- `min_confidence`: default `0.75`
- `min_liquidity`: default `1000.0`
- `max_spread`: default `0.08`
- `min_top_book_size`: default `10.0`
- `orderbook_weight`: default `1.0`
- `display_price_weight`: default `0.5`

### `estimate_fair_probabilities_for_market`

Input:

- `Market`
- `dict[token_id, OrderBook]`
- `AutoFairConfig`

Output:

- `list[FairProbabilityEstimate]`

Behavior:

- Skip closed/inactive markets with unusable estimates.
- For each tokenized outcome:
  - if orderbook has best bid and best ask, probability is `(best_bid + best_ask) / 2`;
  - otherwise use displayed outcome price if available;
  - otherwise return unusable estimate with `missing price`.
- Confidence starts at `1.0` and is reduced by data-quality issues.
- Confidence cannot exceed `0.55` when the estimate comes only from display price.
- `usable` is true only when probability exists and confidence >= `min_confidence`.

### `build_auto_fair_probability_book`

Input:

- `markets`
- `orderbooks_by_market`
- `AutoFairConfig`

Output:

- `FairProbabilityBook`
- `list[FairProbabilityEstimate]`

Only usable estimates enter the book. All estimates remain available for audit/reporting.

### Shadow Pipeline Integration

When `shadow scan` receives no `--fair` path:

1. Fetch orderbooks as it already does.
2. Estimate fair probabilities for the current market from those books.
3. Append `model_estimate` events with estimate details.
4. Build a per-market `FairProbabilityBook`.
5. Candidate generation uses the auto book.

When `--fair` is supplied, existing manual behavior remains available for advanced testing.

## CLI Behavior

Update:

```bash
python -m sports_edge_scanner shadow scan --limit 20 --config shadow_config.json --events shadow_events.jsonl
```

New behavior:

- If `--fair` is omitted, use auto fair estimation.
- If `--fair` is provided, use the manual file.

Add optional:

```bash
python -m sports_edge_scanner shadow scan --auto-fair-min-confidence 0.75
```

Do not require the operator to create or edit `fair_probabilities.json` for normal operation.

## Reporting

Extend shadow reports with:

- `model_estimate_count`
- `usable_model_estimate_count`
- `unusable_model_estimate_count`
- `model_rejections_by_reason`

Dashboard can later display the full model-estimate table. This first implementation can make the JSON report sufficient.

## Safety Properties

- Automatic estimates do not create independent sports prediction edge.
- Low-confidence estimates become `watch`, not candidate trades.
- Manual override remains possible but explicit.
- Every estimate is auditable.
- If data quality is weak, the system runs and explains why it did not trade.

## Testing

Required tests:

- Estimate uses orderbook midpoint when bid/ask are available.
- Estimate falls back to displayed price with lower confidence.
- Closed markets are unusable.
- Wide spread and low liquidity reduce confidence below threshold.
- Auto fair book includes only usable estimates.
- Shadow scan without `--fair` emits `model_estimate` events.
- Shadow scan without usable estimates produces zero candidates and clear report counts.
- Existing manual fair file behavior still works.
- CLI parser accepts `--auto-fair-min-confidence`.
- Full test suite remains green.

## Success Criteria

- A user can run shadow simulation without editing a fair-probability file.
- The system automatically explains why it did or did not produce candidates.
- The baseline model is conservative and auditable.
- No real trading behavior changes.
