from pathlib import Path


def test_shadow_trading_runbook_contains_core_commands_and_boundary():
    text = Path("docs/shadow_trading_runbook.md").read_text(encoding="utf-8")

    assert "shadow init-config" in text
    assert "shadow smoke" in text
    assert "shadow scan" in text
    assert "shadow report" in text
    assert "streamlit run dashboard_app.py" in text
    assert "does not place real orders" in text
