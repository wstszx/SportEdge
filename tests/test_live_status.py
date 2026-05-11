import json

from sports_edge_scanner.core.live_status import build_live_status


def test_live_status_reports_missing_configs_as_not_ready(tmp_path):
    status = build_live_status(
        live_config_path=tmp_path / "live_config.json",
        auth_config_path=tmp_path / "polymarket_auth_config.json",
        environ={},
    )

    assert status["ready"] is False
    assert status["live_config_loaded"] is False
    assert status["auth_config_loaded"] is False
    assert "live config missing" in status["blockers"]
    assert "auth config missing" in status["blockers"]


def test_live_status_requires_live_switches_and_named_environment_values(tmp_path):
    live_config_path = tmp_path / "live_config.json"
    auth_config_path = tmp_path / "polymarket_auth_config.json"
    live_config_path.write_text(
        json.dumps(
            {
                "mode": "live",
                "live_enabled": True,
                "require_confirmation_token": False,
                "confirmation_token": "confirm-live",
                "kill_switch_enabled": False,
                "max_order_notional": 10.0,
                "max_market_exposure": 25.0,
                "max_total_exposure": 100.0,
                "daily_loss_limit": 25.0,
                "allowed_venues": ["polymarket"],
            }
        ),
        encoding="utf-8",
    )
    auth_config_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "host": "https://clob.polymarket.com",
                "chain_id": 137,
                "signature_type": 0,
                "funder_env": "FUNDER",
                "private_key_env": "PRIVATE_KEY",
                "api_key_env": "API_KEY",
                "api_secret_env": "API_SECRET",
                "api_passphrase_env": "API_PASSPHRASE",
                "require_geoblock_check": True,
                "allow_live_writes": True,
            }
        ),
        encoding="utf-8",
    )

    status = build_live_status(
        live_config_path=live_config_path,
        auth_config_path=auth_config_path,
        environ={
            "FUNDER": "0xabc",
            "PRIVATE_KEY": "secret-private-key",
            "API_KEY": "secret-api-key",
            "API_SECRET": "secret-api-secret",
            "API_PASSPHRASE": "secret-passphrase",
        },
    )

    serialized = json.dumps(status, sort_keys=True)
    assert status["ready"] is True
    assert status["blockers"] == []
    assert status["mode"] == "live"
    assert status["live_enabled"] is True
    assert status["kill_switch_enabled"] is False
    assert status["auth_enabled"] is True
    assert status["allow_live_writes"] is True
    assert status["credential_status"] == "present"
    assert status["missing_credential_envs"] == []
    assert "secret-private-key" not in serialized
    assert "secret-api-key" not in serialized


def test_live_status_lists_blockers_without_secret_values(tmp_path):
    live_config_path = tmp_path / "live_config.json"
    auth_config_path = tmp_path / "polymarket_auth_config.json"
    live_config_path.write_text(
        json.dumps(
            {
                "mode": "dry_run",
                "live_enabled": False,
                "require_confirmation_token": True,
                "confirmation_token": "confirm-live",
                "kill_switch_enabled": True,
                "max_order_notional": 10.0,
                "max_market_exposure": 25.0,
                "max_total_exposure": 100.0,
                "daily_loss_limit": 25.0,
                "allowed_venues": ["polymarket"],
            }
        ),
        encoding="utf-8",
    )
    auth_config_path.write_text(
        json.dumps(
            {
                "enabled": False,
                "host": "https://clob.polymarket.com",
                "chain_id": 137,
                "signature_type": 0,
                "funder_env": "FUNDER",
                "private_key_env": "PRIVATE_KEY",
                "api_key_env": "API_KEY",
                "api_secret_env": "API_SECRET",
                "api_passphrase_env": "API_PASSPHRASE",
                "require_geoblock_check": True,
                "allow_live_writes": False,
            }
        ),
        encoding="utf-8",
    )

    status = build_live_status(
        live_config_path=live_config_path,
        auth_config_path=auth_config_path,
        environ={"PRIVATE_KEY": "secret-private-key"},
    )

    assert status["ready"] is False
    assert "live mode is not live" in status["blockers"]
    assert "live mode disabled" in status["blockers"]
    assert "kill switch enabled" in status["blockers"]
    assert "confirmation token required" in status["blockers"]
    assert "auth config disabled" in status["blockers"]
    assert "live writes disabled" in status["blockers"]
    assert set(status["missing_credential_envs"]) == {
        "FUNDER",
        "API_KEY",
        "API_SECRET",
        "API_PASSPHRASE",
    }
    assert "secret-private-key" not in json.dumps(status, sort_keys=True)
