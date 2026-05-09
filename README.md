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
- candidate signals only when a fair probability is supplied and clears the configured edge threshold;
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
