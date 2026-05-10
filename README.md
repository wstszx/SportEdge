# Sports Edge Scanner

Sports Edge Scanner is a research-only CLI for scanning public prediction-market data, estimating break-even probabilities, flagging risk-aware candidates, and recording paper trades.

It does not place real bets, manage wallets, bypass platform restrictions, or claim that positive EV guarantees profit. Treat every signal as a hypothesis that needs validation through closing-line value, calibration, drawdown, and enough sample size.

## Usage

```bash
python -m sports_edge_scanner scan --limit 20
python -m sports_edge_scanner scan --limit 20 --json
python -m sports_edge_scanner scan --limit 20 --fair YES=0.55
python -m sports_edge_scanner paper add --market "Example market" --side YES --price 0.47 --size 10 --note "tracking candidate"
python -m sports_edge_scanner paper settle --market "Example market" --market-id "0xabc..." --winning-side YES --note "resolved"
python -m sports_edge_scanner snapshot collect --limit 50
python -m sports_edge_scanner snapshot watch --limit 50 --iterations 48 --interval-seconds 1800
python -m sports_edge_scanner quality
python -m sports_edge_scanner report
```

## What The Scanner Reports

- current YES/NO prices when available;
- implied and break-even probabilities;
- liquidity and spread warnings;
- candidate signals only when model input clears the configured edge threshold;
- conservative fractional Kelly sizing for positive-edge inputs.

## Safety Defaults

- No automated betting.
- No private-key or wallet support.
- Missing prices or low liquidity become warnings.
- Kelly sizing returns zero when the edge is not positive.
- The default Kelly output uses a 0.25 fraction and a 5% bankroll cap.

## Validation Workflow

Use snapshots and paper trades to check whether a signal has evidence, not just a nice-looking EV number.

```bash
python -m sports_edge_scanner snapshot collect --limit 50 --snapshots market_snapshots.jsonl
python -m sports_edge_scanner paper add --market "0xabc..." --market-id "0xabc..." --side YES --price 0.47 --size 25 --note "manual fair probability 55%"
python -m sports_edge_scanner snapshot collect --limit 50 --snapshots market_snapshots.jsonl
python -m sports_edge_scanner quality --ledger paper_trades.jsonl --snapshots market_snapshots.jsonl
python -m sports_edge_scanner report --ledger paper_trades.jsonl --snapshots market_snapshots.jsonl
```

The report uses the latest snapshot price as a mark-to-market price. For a YES paper trade, positive CLV means the latest YES price is above the entry price. For a NO paper trade, positive CLV means the latest NO price is above the entry price.

Run `quality` before trusting the report. It shows snapshot count, market count, total time span, candidate snapshot count, missing price snapshots, and paper trades that cannot be matched to any collected market.

After a market resolves, record the result:

```bash
python -m sports_edge_scanner paper settle --market "0xabc..." --market-id "0xabc..." --winning-side YES --note "official resolution"
python -m sports_edge_scanner report --ledger paper_trades.jsonl --snapshots market_snapshots.jsonl
```

Settlement records let the report calculate realized PnL, realized ROI, win rate, and max drawdown. Unsettled trades still use mark-to-market pricing when matching snapshots are available.

For unattended collection, run a bounded watch loop:

```bash
python -m sports_edge_scanner snapshot watch --limit 50 --iterations 48 --interval-seconds 1800 --snapshots market_snapshots.jsonl
```

That collects 48 snapshots, one every 30 minutes. Prefer bounded runs so failures are visible and logs stay manageable.

## Local Dashboard

Install the optional dashboard dependencies:

```bash
python -m pip install -e .[dashboard]
```

Launch the local research UI:

```bash
streamlit run dashboard_app.py
```

The dashboard reads the same JSONL files as the CLI. It shows overview metrics, latest markets, price history, paper trades, settlements, data-quality checks, and raw report JSON. It is still research-only and does not place orders.

## Shadow Trading Simulation

Shadow mode rehearses live-trading decisions without sending real orders, signing payloads, storing private keys, or controlling funds.

Run a bounded shadow scan:

```bash
python -m sports_edge_scanner shadow scan --limit 20 --events shadow_events.jsonl
python -m sports_edge_scanner shadow report --events shadow_events.jsonl
```

When `--fair` is omitted, shadow mode automatically builds conservative fair
probability estimates from public orderbook and market data. Estimates include
source, confidence, and rejection reasons in the event log. Low-confidence
estimates do not generate candidate trades.

Manual fair probability files are an advanced override for controlled tests:

```json
{
  "markets": {
    "example-market-slug": {
      "Team A": 0.57
    }
  },
  "tokens": {
    "example-token-id": 0.57
  }
}
```

```bash
python -m sports_edge_scanner shadow scan --limit 20 --fair fair_probabilities.json --events shadow_events.jsonl
```

Every candidate is either rejected with explicit risk reasons or converted into
a simulated limit order and fill record. The report also includes an automatic
readiness verdict with blockers and thresholds. `READY` means the paper evidence
is adequate for the next design review; it is not permission to trade live.
Shadow results are not live fills and should be treated as research evidence
only.

Create safe starter files:

```bash
python -m sports_edge_scanner shadow init-config
```

This writes `shadow_config.json` and `fair_probabilities.example.json` unless they already exist. Use `--force` only when you intentionally want to overwrite them.

## Live Safety Core

The `live` command group is a safety scaffold for future real execution. In this phase it still does not place real orders, cancel orders, sign payloads, load private keys, or manage wallets.

Create the safe default config:

```bash
python -m sports_edge_scanner live init-config
```

Check the config:

```bash
python -m sports_edge_scanner live check-config --config live_config.json
```

Run an audited dry-run through the live safety guard:

```bash
python -m sports_edge_scanner live dry-run --events execution_events.jsonl --confirm-token confirm-live-dry-run
```

The default config keeps the kill switch enabled, so dry-run execution is rejected until the operator explicitly disables it in a local config file. Real venue execution requires a later authenticated adapter design.

## Polymarket Auth Readiness

The `polymarket-auth` command group checks whether a future authenticated adapter is configured safely. It does not place real orders and does not accept private keys or API secrets as command-line arguments.

Create a non-secret config template:

```bash
python -m sports_edge_scanner polymarket-auth init-config
```

Check local readiness:

```bash
python -m sports_edge_scanner polymarket-auth check --config polymarket_auth_config.json
```

Check geographic restriction status:

```bash
python -m sports_edge_scanner polymarket-auth geoblock --json
```

Credential values must come from environment variables named in the config. The config file stores only environment variable names and safety flags. If the geoblock check reports blocked, the adapter must reject authenticated writes.
