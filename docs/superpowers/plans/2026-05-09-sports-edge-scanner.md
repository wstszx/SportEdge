# Sports Edge Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that scans Polymarket sports-like markets, computes risk-aware betting signals, and records paper-trading decisions without placing real orders.

**Architecture:** Keep network IO at the connector edge and put pricing, Kelly, signal classification, and ledger behavior in pure modules. The CLI composes those modules and can render either text or JSON output.

**Tech Stack:** Python 3.11+, standard library `argparse`, `dataclasses`, `json`, `urllib`; `pytest` for tests.

---

## File Structure

- `pyproject.toml`: package metadata and pytest configuration.
- `README.md`: usage, safety limits, and examples.
- `sports_edge_scanner/__init__.py`: package version.
- `sports_edge_scanner/models.py`: shared dataclasses and validation helpers.
- `sports_edge_scanner/core/pricing.py`: price/probability math.
- `sports_edge_scanner/core/kelly.py`: conservative Kelly sizing.
- `sports_edge_scanner/core/signals.py`: signal classification.
- `sports_edge_scanner/core/ledger.py`: JSONL paper ledger.
- `sports_edge_scanner/connectors/polymarket.py`: public Polymarket market fetcher and normalizer.
- `sports_edge_scanner/cli.py`: command-line interface.
- `tests/test_pricing.py`: pricing tests.
- `tests/test_kelly.py`: Kelly tests.
- `tests/test_signals.py`: signal tests.
- `tests/test_ledger.py`: ledger tests.
- `tests/test_polymarket_connector.py`: mocked connector tests.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `sports_edge_scanner/__init__.py`
- Create: `sports_edge_scanner/core/__init__.py`
- Create: `sports_edge_scanner/connectors/__init__.py`

- [ ] **Step 1: Create package metadata**

`pyproject.toml` should define a setuptools package with a `sports-edge-scanner` console script pointing at `sports_edge_scanner.cli:main`.

- [ ] **Step 2: Create a focused README**

`README.md` should explain that the tool is research-only, show `scan` and `paper add` examples, and state that positive EV is not guaranteed profit.

- [ ] **Step 3: Create package init files**

Add empty package directories plus `__version__ = "0.1.0"`.

- [ ] **Step 4: Run package discovery check**

Run: `python -m pytest --version`

Expected: pytest is available or reports a clear missing-package error before test work begins.

## Task 2: Pricing Core

**Files:**
- Create: `sports_edge_scanner/core/pricing.py`
- Test: `tests/test_pricing.py`

- [ ] **Step 1: Write failing tests**

Test implied probability, break-even probability with a cost buffer, expected value per unit, and invalid price validation.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_pricing.py -q`

Expected: FAIL because `sports_edge_scanner.core.pricing` does not exist.

- [ ] **Step 3: Implement minimal pricing functions**

Add:

- `validate_price(price: float) -> float`
- `implied_probability(price: float) -> float`
- `break_even_probability(price: float, cost_buffer: float = 0.0) -> float`
- `expected_value_per_unit(fair_probability: float, price: float, cost_buffer: float = 0.0) -> float`

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_pricing.py -q`

Expected: PASS.

## Task 3: Kelly Core

**Files:**
- Create: `sports_edge_scanner/core/kelly.py`
- Test: `tests/test_kelly.py`

- [ ] **Step 1: Write failing tests**

Test zero sizing for no edge, fractional Kelly sizing for a valid edge, and validation of bad probabilities/prices.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_kelly.py -q`

Expected: FAIL because `sports_edge_scanner.core.kelly` does not exist.

- [ ] **Step 3: Implement minimal Kelly functions**

Add:

- `kelly_fraction(fair_probability: float, price: float) -> float`
- `fractional_kelly(fair_probability: float, price: float, fraction: float = 0.25, cap: float = 0.05) -> float`

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_kelly.py -q`

Expected: PASS.

## Task 4: Models and Signals

**Files:**
- Create: `sports_edge_scanner/models.py`
- Create: `sports_edge_scanner/core/signals.py`
- Test: `tests/test_signals.py`

- [ ] **Step 1: Write failing tests**

Test classification for missing prices, wide spread, low liquidity, and a candidate with fair probability above the edge threshold.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_signals.py -q`

Expected: FAIL because models/signals do not exist.

- [ ] **Step 3: Implement shared models and signal classifier**

Add dataclasses:

- `MarketOutcome`
- `Market`
- `Signal`

Add:

- `classify_market(market: Market, fair_probabilities: dict[str, float] | None = None, min_edge: float = 0.02, min_liquidity: float = 1000.0, max_spread: float = 0.08) -> Signal`

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_signals.py -q`

Expected: PASS.

## Task 5: Paper Ledger

**Files:**
- Create: `sports_edge_scanner/core/ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write failing tests**

Test appending a paper trade to JSONL and reading it back.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_ledger.py -q`

Expected: FAIL because ledger module does not exist.

- [ ] **Step 3: Implement ledger functions**

Add:

- `paper_trade_record(...) -> dict[str, object]`
- `append_record(path: Path, record: dict[str, object]) -> None`
- `read_records(path: Path) -> list[dict[str, object]]`

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_ledger.py -q`

Expected: PASS.

## Task 6: Polymarket Connector

**Files:**
- Create: `sports_edge_scanner/connectors/polymarket.py`
- Test: `tests/test_polymarket_connector.py`

- [ ] **Step 1: Write failing mocked connector tests**

Mock `urllib.request.urlopen` and test that a Gamma API response is normalized into `Market` objects with YES and NO prices.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_polymarket_connector.py -q`

Expected: FAIL because connector module does not exist.

- [ ] **Step 3: Implement connector**

Add:

- `PolymarketClient`
- `fetch_markets(limit: int = 50, active: bool = True) -> list[Market]`
- sports-like filtering based on tags, category, and market title keywords.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_polymarket_connector.py -q`

Expected: PASS.

## Task 7: CLI

**Files:**
- Create: `sports_edge_scanner/cli.py`
- Modify: `README.md`

- [ ] **Step 1: Implement CLI commands**

Add:

- `scan --limit --json`
- `paper add --ledger --market --side --price --size --note`

- [ ] **Step 2: Run CLI smoke checks**

Run:

```bash
python -m sports_edge_scanner --help
python -m sports_edge_scanner paper add --ledger .tmp-paper.jsonl --market "Example" --side YES --price 0.47 --size 10 --note "tracking"
```

Expected: help text prints and `.tmp-paper.jsonl` receives one JSONL record.

- [ ] **Step 3: Remove smoke ledger file**

Delete `.tmp-paper.jsonl` after confirming CLI behavior.

## Task 8: Full Verification

**Files:**
- All project files.

- [ ] **Step 1: Run test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 2: Run scan smoke command**

Run: `python -m sports_edge_scanner scan --limit 5 --json`

Expected: command exits cleanly and prints JSON. If the network request fails, it must print a clear error and exit non-zero.

- [ ] **Step 3: Review git diff**

Run: `git diff --stat`

Expected: only project scaffold, docs, source, and tests are changed.
