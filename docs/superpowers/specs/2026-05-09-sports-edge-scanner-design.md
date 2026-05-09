# Sports Edge Scanner Design

## Goal

Build a conservative sports betting research tool that scans public prediction-market data, computes market-implied prices, flags risk-aware opportunities, and records paper-trading decisions. The first version is a signal and validation framework, not an automated betting bot.

## Scope

Version one focuses on Polymarket public data because Gamma can discover markets and CLOB can provide market pricing without private credentials. The code keeps connector boundaries open so Kalshi, odds APIs, exchange books, or user-supplied model probabilities can be added later.

The tool does not place orders, manage wallets, bypass geographic restrictions, or claim that positive expected value guarantees profit. It reports candidates, required break-even probabilities, conservative Kelly sizing, liquidity warnings, and paper-trading records.

## Architecture

The project is a Python CLI package named `sports_edge_scanner`.

- `connectors.polymarket` fetches public Polymarket markets and normalizes them.
- `core.pricing` converts prices into implied probabilities and break-even thresholds.
- `core.kelly` computes conservative Kelly fractions when the user provides a fair probability.
- `core.signals` classifies markets as watch, candidate, or skip using liquidity, spread, and optional fair-probability inputs.
- `core.ledger` appends paper-trade records to local JSONL.
- `cli` exposes commands for scanning and recording paper trades.

Each module has a narrow interface so the scanner can be tested without network calls.

## Data Flow

1. The CLI asks the Polymarket connector for active sports-like markets.
2. The connector returns normalized market objects with title, slug, end time, outcomes, prices, liquidity, volume, and condition token identifiers when available.
3. The pricing engine computes implied probabilities and break-even probabilities after an optional cost buffer.
4. The signal engine applies filters:
   - skip closed or unresolved markets;
   - warn on low liquidity;
   - warn on wide YES/NO spread;
   - mark markets as candidates only when there is enough price data and the user-supplied fair probability clears the configured edge threshold.
5. The CLI prints a compact table or JSON output.
6. The ledger can record a paper decision with timestamp, side, price, size, rationale, and metadata.

## Risk Rules

The default behavior is deliberately cautious:

- no automatic betting;
- no signal marked as actionable without a minimum edge threshold;
- no Kelly output without a fair probability supplied by the user or a future model connector;
- fractional Kelly defaults to 0.25;
- negative or zero EV returns a zero stake suggestion;
- missing liquidity, missing prices, or inconsistent outcome data produce warnings instead of confident signals.

## CLI

Initial commands:

```bash
python -m sports_edge_scanner scan --limit 20
python -m sports_edge_scanner scan --json --limit 20
python -m sports_edge_scanner paper add --market "Example" --side YES --price 0.47 --size 10 --note "tracking candidate"
```

The scan command should still be useful when no fair probabilities are supplied: it reports break-even probabilities and risk tags rather than pretending to know the true probability.

## Testing

Tests cover pure core behavior first:

- implied probability and break-even calculations;
- Kelly sizing, including bad inputs and conservative fractional sizing;
- signal classification for missing prices, wide spreads, low liquidity, and positive-edge candidates;
- JSONL paper ledger append/read behavior.

Network connector tests use mocked HTTP responses. A live network smoke test is optional and is not required for the normal test suite.

## Non-Goals

- Automated order placement.
- Wallet/private-key handling.
- Legal or tax advice.
- Guaranteeing profitability.
- Building a sports prediction model in version one.
