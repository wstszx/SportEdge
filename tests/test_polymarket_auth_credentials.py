import json

import pytest

from sports_edge_scanner.connectors.polymarket_auth import (
    EnvironmentPolymarketCredentialProvider,
    PolymarketCredentials,
    load_polymarket_auth_config,
    write_polymarket_auth_config_template,
)


def test_credentials_redact_secret_values():
    credentials = PolymarketCredentials(
        private_key="secret-private",
        api_key="secret-key",
        api_secret="secret-api-secret",
        api_passphrase="secret-passphrase",
        funder="0xfunder",
        signature_type=0,
    )

    payload = credentials.to_dict()

    assert payload == {
        "private_key": "<redacted>",
        "api_key": "<redacted>",
        "api_secret": "<redacted>",
        "api_passphrase": "<redacted>",
        "funder": "0xfunder",
        "signature_type": 0,
    }
    assert "secret" not in repr(credentials)


def test_environment_provider_loads_required_values(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "private")
    monkeypatch.setenv("POLYMARKET_API_KEY", "key")
    monkeypatch.setenv("POLYMARKET_API_SECRET", "secret")
    monkeypatch.setenv("POLYMARKET_API_PASSPHRASE", "pass")
    monkeypatch.setenv("POLYMARKET_FUNDER", "0xfunder")
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "1")

    credentials = EnvironmentPolymarketCredentialProvider().load()

    assert credentials.funder == "0xfunder"
    assert credentials.signature_type == 1
    assert credentials.private_key == "private"


def test_environment_provider_rejects_missing_values(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)

    with pytest.raises(ValueError, match="missing credential environment variables"):
        EnvironmentPolymarketCredentialProvider().load()


def test_auth_config_template_contains_env_names_not_secrets(tmp_path):
    path = tmp_path / "polymarket_auth_config.json"

    write_polymarket_auth_config_template(path)
    loaded = load_polymarket_auth_config(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert loaded.enabled is False
    assert loaded.allow_live_writes is False
    assert payload["private_key_env"] == "POLYMARKET_PRIVATE_KEY"
    assert "secret-private" not in path.read_text(encoding="utf-8")
    assert "api_secret_env" in payload
