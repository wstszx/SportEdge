# Shadow Trading Runbook

Sports Edge Scanner shadow mode is a research workflow. It does not place real orders, sign payloads, manage wallets, cancel orders, or control funds.

## 1. Start The App

```bash
python -m sports_edge_scanner app
```

Use the Control tab to configure and run paper/shadow collection. The app is
the normal operator workflow.

## 2. Run Paper/Shadow Collection

In the Control tab, set:

- shadow events path;
- shadow config path;
- market limit;
- collection iterations;
- interval seconds;
- automatic fair-probability confidence threshold.

Then choose a quick one-iteration scan or bounded paper collection. Each
iteration receives a separate run id and appends to the same event log. If an
iteration fails, the app records a `shadow_scan_error` event.

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

`READY` is not live-trading permission. It only means the shadow evidence is
clean enough to consider the next safety design step.

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
