from pathlib import Path


def test_shadow_trading_runbook_contains_core_commands_and_boundary():
    text = Path("docs/shadow_trading_runbook.md").read_text(encoding="utf-8")

    assert "python -m sports_edge_scanner app" in text
    assert "Control tab" in text
    assert "shadow smoke" in text
    assert "does not place real orders" in text
