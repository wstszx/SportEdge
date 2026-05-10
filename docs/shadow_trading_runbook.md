# Shadow Trading Runbook

Sports Edge Scanner shadow mode is a research workflow. It does not place real orders, sign payloads, manage wallets, cancel orders, or control funds.

## 1. Create Starter Files

```bash
python -m sports_edge_scanner shadow init-config
```

This creates `shadow_config.json` and `fair_probabilities.example.json` unless
they already exist. `shadow_config.json` controls risk limits.

## 2. Check Public Data

```bash
python -m sports_edge_scanner shadow smoke --limit 2
python -m sports_edge_scanner shadow smoke --limit 2 --json
```

Run the smoke check before longer scans. It verifies that public Gamma market
data and public CLOB orderbook data can be fetched without credentials. A
non-zero exit means the data source is unavailable, no usable markets were
found, no token ids were available, or orderbook fetches failed.

## 3. Run A Shadow Scan

```bash
python -m sports_edge_scanner shadow scan --limit 20 --config shadow_config.json --events shadow_events.jsonl
```

When `--fair` is omitted, the scanner automatically creates conservative fair
probability estimates from public orderbook and market data. Each estimate is
written as a `model_estimate` event with source, confidence, usability, and
reasons. Low-confidence estimates stay in watch mode and do not create
candidate trades.

Each candidate is either rejected by risk controls or simulated as a limit order
against observed orderbook depth. The scan writes append-only events to
`shadow_events.jsonl`.

## 4. Optional Manual Fair Override

Copy `fair_probabilities.example.json` to `fair_probabilities.json`, then enter
independent fair probabilities by market/outcome or token id only when running
controlled tests. Treat these probabilities as model inputs, not facts. They
need independent evidence, calibration, and sample-size review before the
output should influence real trading decisions.

```bash
python -m sports_edge_scanner shadow scan --limit 20 --fair fair_probabilities.json --config shadow_config.json --events shadow_events.jsonl
```

## 5. Review The Report

```bash
python -m sports_edge_scanner shadow report --events shadow_events.jsonl
python -m sports_edge_scanner shadow report --events shadow_events.jsonl --json
```

Review model estimate count, usable and unusable estimates, candidate count,
accepted and rejected shadow orders, filled and unfilled notional, exposure by
market, exposure by outcome, average slippage, and data quality warnings.

## 6. Open The Dashboard

```bash
streamlit run dashboard_app.py
```

Set the ledger, market snapshot, and shadow events paths in the sidebar. Use the
Shadow tab to inspect exposure, risk decisions, fills, warnings, and raw report
JSON.

## 7. Warnings That Make Results Unreliable

- `orderbook errors present`: the run did not observe all candidate liquidity.
- `rejected orders present`: risk controls blocked one or more candidates.
- `unfilled shadow orders present`: configured limits exceeded available depth.
- `candidates present but no fills`: signals were generated but no simulated
  executions occurred.
- `no usable model estimates`: automatic probabilities were too weak to trade.
- Stale orderbooks mean pricing may not represent current executable depth.
- Fair probabilities without calibration or sample-size evidence should not be
  trusted.

Do not use shadow results as production evidence when warnings are present,
when fills are missing, when public API smoke checks fail, or when fair
probabilities have not been independently validated.
