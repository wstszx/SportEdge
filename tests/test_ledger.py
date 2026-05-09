import json
import pytest

from sports_edge_scanner.core.ledger import (
    append_record,
    paper_settlement_record,
    paper_trade_record,
    read_records,
)


def test_append_record_writes_jsonl_and_read_records_loads_it(tmp_path):
    ledger_path = tmp_path / "paper.jsonl"
    record = paper_trade_record(
        market="Team A vs Team B",
        side="YES",
        price=0.47,
        size=10.0,
        note="tracking candidate",
    )

    append_record(ledger_path, record)

    raw_line = ledger_path.read_text(encoding="utf-8").strip()
    assert json.loads(raw_line)["market"] == "Team A vs Team B"
    assert json.loads(raw_line)["type"] == "trade"
    assert read_records(ledger_path) == [record]


def test_read_records_returns_empty_list_for_missing_ledger(tmp_path):
    assert read_records(tmp_path / "missing.jsonl") == []


def test_paper_settlement_record_captures_winning_side_and_market_id():
    record = paper_settlement_record(
        market="Team A vs Team B",
        market_id="market-1",
        winning_side="YES",
        note="resolved yes",
        timestamp="2026-05-09T00:00:00+00:00",
    )

    assert record == {
        "type": "settlement",
        "timestamp": "2026-05-09T00:00:00+00:00",
        "market": "Team A vs Team B",
        "market_id": "market-1",
        "winning_side": "YES",
        "note": "resolved yes",
    }


@pytest.mark.parametrize("winning_side", ["MAYBE", ""])
def test_paper_settlement_record_rejects_invalid_winning_side(winning_side):
    with pytest.raises(ValueError):
        paper_settlement_record(
            market="Team A vs Team B",
            market_id="market-1",
            winning_side=winning_side,
        )
