from pathlib import Path


def test_shadow_trading_runbook_contains_core_commands_and_boundary():
    text = Path("docs/shadow_trading_runbook.md").read_text(encoding="utf-8")

    assert "python -m sports_edge_scanner app" in text
    assert "Control tab" in text
    assert "仅纸面" in text
    assert "仅实盘" in text
    assert "纸面+实盘" in text
    assert "shadow smoke" in text
    assert "does not place real orders" in text


def test_readme_documents_frontend_run_mode_switching():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "仅纸面" in text
    assert "仅实盘" in text
    assert "纸面+实盘" in text
    assert "自动采集" in text
    assert "same signal, risk, and order-generation pipeline" in text
    assert "paper mode" in text
    assert "allow_live_writes" in text
