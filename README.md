# Sports Edge Scanner

Sports Edge Scanner is a research-only local app for scanning public prediction-market data, estimating break-even probabilities, flagging risk-aware candidates, and recording paper trades.

It does not place real bets, manage wallets, bypass platform restrictions, or claim that positive EV guarantees profit. Treat every signal as a hypothesis that needs validation through closing-line value, calibration, drawdown, and enough sample size.

## Usage

Start here:

```bash
python -m sports_edge_scanner app
```

Use the frontend Control tab to configure and run paper/shadow collection,
quick scans, and readiness review. Lower-level CLI commands still exist for
tests and automation, but the normal operator workflow is the app.

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

## Local App

The dashboard reads the same JSONL files as the CLI. It shows overview metrics,
latest markets, price history, paper trades, settlements, data-quality checks,
shadow readiness, a Control tab for bounded shadow collection, and raw report
JSON. It is still research-only and does not place orders.

## Paper And Shadow Workflow

Shadow mode rehearses live-trading decisions without sending real orders, signing payloads, storing private keys, or controlling funds.

Use the frontend Control tab to run a quick scan or bounded shadow collection.
Collection runs append events to `shadow_events.jsonl`, record failed iterations
as `shadow_scan_error`, and update the readiness verdict shown in the app.

When `--fair` is omitted, shadow mode automatically builds conservative fair
probability estimates from public orderbook and market data. Estimates include
source, confidence, and rejection reasons in the event log. Low-confidence
estimates do not generate candidate trades.

Manual fair probability files are an advanced override for controlled tests and
are not required for normal app usage:

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

Every candidate is either rejected with explicit risk reasons or converted into
a simulated limit order and fill record. The report also includes an automatic
readiness verdict with blockers and thresholds. `READY` means the paper evidence
is adequate for the next design review; it is not permission to trade live.
Shadow results are not live fills and should be treated as research evidence
only.

## Live Safety Core

The live safety layer is a scaffold for future real execution. In this phase it
still does not place real orders, cancel orders, sign payloads, load private
keys, or manage wallets. The app shows live safety status as read-only context;
real venue execution requires a later authenticated execution design.

## Polymarket Auth Readiness

Authenticated Polymarket support is readiness-only. It does not place real
orders and does not accept private keys or API secrets as command-line
arguments. Credential values must come from environment variables named in
local config files, and geographic restrictions must block authenticated writes.

## Advanced CLI

The lower-level CLI commands such as `shadow scan`, `shadow watch`, `shadow
report`, `live dry-run`, and `polymarket-auth check` remain available for tests,
automation, and debugging. They are not the normal operator workflow. Start with:

```bash
python -m sports_edge_scanner app
```
