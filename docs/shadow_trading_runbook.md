# Shadow Trading Runbook

Sports Edge Scanner shadow mode is a research workflow. It does not place real orders unless you explicitly switch the frontend to live mode and enable both live safety and Polymarket auth configs. Paper/shadow mode does not submit orders, cancel orders, or control funds.

## 1. Start The App

```bash
python -m sports_edge_scanner app
```

Use the Control tab to switch the running mode directly: `仅纸面`, `仅实盘`,
or `纸面+实盘`. The app is the normal operator workflow. Use the `实盘执行`
tab to review live readiness, config blockers, submitted orders, rejected
orders, and the latest execution status.

## 2. Choose A Running Mode

In the Control tab, choose one mode and press the start button:

- `仅纸面`: automatically collect market data, then run the paper/shadow workflow.
- `仅实盘`: automatically collect market data, then run the same signal and
  risk flow with real execution enabled by config.
- `纸面+实盘`: automatically collect market data, then run both workflows.

Data fetching is automatic for all three modes. File paths, limits, iterations,
and thresholds remain available under Advanced Settings for tests or unusual
local setups, but they are not part of the normal operator workflow.

Each paper/shadow iteration receives a separate run id and appends to the same
event log. If an iteration fails, the app records a `shadow_scan_error` event.

## 3. Review Readiness

When `--fair` is omitted, the scanner automatically creates conservative fair
probability estimates from public orderbook and market data. Each estimate is
written as a `model_estimate` event with source, confidence, usability, and
reasons. Low-confidence estimates stay in watch mode and do not create
candidate trades.

Each candidate is either rejected by risk controls or simulated as a limit order
against observed orderbook depth. The scan writes append-only events to
`shadow_events.jsonl`.

The Shadow and Control tabs show the readiness verdict:

- `READY`: paper evidence meets the configured gate for the next design review.
- `NOT READY`: blockers explain what evidence is missing or unreliable.

`READY` is not enough by itself to place live orders. Live execution also
requires explicitly enabled live and Polymarket auth configs. The `实盘执行`
tab shows those live-specific blockers separately from paper readiness.

## 4. Optional Manual Fair Override

Copy `fair_probabilities.example.json` to `fair_probabilities.json`, then enter
independent fair probabilities by market/outcome or token id only when running
controlled tests. Treat these probabilities as model inputs, not facts. They
need independent evidence, calibration, and sample-size review before the
output should influence real trading decisions.

## 5. Warnings That Make Results Unreliable

- `orderbook errors present`: the run did not observe all candidate liquidity.
- `rejected orders present`: risk controls blocked one or more candidates.
- `unfilled shadow orders present`: configured limits exceeded available depth.
- `candidates present but no fills`: signals were generated but no simulated
  executions occurred.
- `no usable model estimates`: automatic probabilities were too weak to trade.
- `shadow scan errors present`: one or more watch iterations failed.
- Stale orderbooks mean pricing may not represent current executable depth.
- Fair probabilities without calibration or sample-size evidence should not be
  trusted.
- A `READY` readiness verdict is only a review gate. It does not override live
  safety controls.

Do not use shadow results as production evidence when warnings are present,
when fills are missing, when public API smoke checks fail, or when fair
probabilities have not been independently validated.

## Advanced CLI

Lower-level commands such as `shadow smoke`, `shadow scan`, `shadow watch`, and
`shadow report` remain available for tests and automation. They are not the
normal operator workflow.
