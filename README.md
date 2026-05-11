# Sports Edge Scanner

Sports Edge Scanner is a local prediction-market research and execution app for scanning public data, estimating break-even probabilities, flagging risk-aware candidates, recording paper trades, and optionally routing approved live orders when explicit live configs are enabled.

By default it does not place real bets or manage wallets. Live order submission
is possible only after you explicitly enable both live safety and Polymarket
auth configs. It does not bypass platform restrictions or claim that positive EV
guarantees profit. Treat every signal as a hypothesis that needs validation
through closing-line value, calibration, drawdown, and enough sample size.

## Usage

Start here:

```bash
python -m sports_edge_scanner app
```

Use the frontend Control tab to switch the running mode directly:

- `仅纸面`
- `仅实盘`
- `纸面+实盘`

After you press the start button, the app automatically collects the market data
needed by the selected mode and then runs the matching workflow. In short, data
fetching is 自动采集. Lower-level CLI commands still exist for tests and
automation, but the normal operator workflow is the app mode switch.

## What The Scanner Reports

- current YES/NO prices when available;
- implied and break-even probabilities;
- liquidity and spread warnings;
- candidate signals only when model input clears the configured edge threshold;
- conservative fractional Kelly sizing for positive-edge inputs.

## Safety Defaults

- Real execution is available only when live and Polymarket auth configs are
  explicitly enabled.
- No private keys or API secrets are accepted through the frontend or CLI.
- Missing prices or low liquidity become warnings.
- Kelly sizing returns zero when the edge is not positive.
- The default Kelly output uses a 0.25 fraction and a 5% bankroll cap.

## Local App

The dashboard reads the same JSONL files as the CLI. It shows overview metrics,
latest markets, price history, paper trades, settlements, data-quality checks,
shadow readiness, a Control tab for mode switching, a `实盘执行` tab for live
readiness and execution audit status, and raw report JSON. In live mode, the app
uses the same signal, risk, and order-generation pipeline as paper mode; only
the final execution client changes.

## Paper And Shadow Workflow

Shadow mode rehearses live-trading decisions without sending real orders, signing payloads, storing private keys, or controlling funds.

Use the frontend Control tab to choose `仅纸面`, `仅实盘`, or `纸面+实盘`.
The app handles automatic data collection, or 自动采集, before running the
selected workflow.
Paper collection runs append events to `shadow_events.jsonl`, record failed
iterations as `shadow_scan_error`, and update the readiness verdict shown in the
app.

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

## Live Execution

Live execution uses the same market fetch, orderbook fetch, automatic fair
probability, candidate generation, and risk checks as paper/shadow execution.
The only intended behavioral difference is the final execution step:

- paper mode writes simulated `shadow_order` and `shadow_fill` events;
- live mode writes audited execution events and submits approved orders through
  the authenticated Polymarket CLOB client.

Real orders are submitted only when both local configs are explicitly enabled:

- `live_config.json`: `mode` is `live`, `live_enabled` is `true`, and the kill
  switch is disabled;
- `polymarket_auth_config.json`: `enabled` and `allow_live_writes` are both
  `true`;
- credential environment variables named in `polymarket_auth_config.json` are
  present.

Credential values are loaded from environment variables, not command-line
arguments, and event logs store only sanitized execution status. The dashboard
`实盘执行` tab summarizes whether live mode is ready, which safety/config
blockers remain, how many orders were submitted or rejected, and the latest
execution status.

## Polymarket Auth Readiness

Authenticated Polymarket support can place real orders only through the live
execution pipeline above. Private keys and API secrets are not accepted as
command-line arguments. Credential values must come from environment variables
named in local config files, and geographic restrictions must block
authenticated writes.

## Advanced CLI

The lower-level CLI commands such as `shadow scan`, `shadow watch`, `shadow
report`, `live dry-run`, and `polymarket-auth check` remain available for tests,
automation, and debugging. They are not the normal operator workflow. Start with:

```bash
python -m sports_edge_scanner app
```
