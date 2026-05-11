import os
from pathlib import Path
from typing import Mapping

from sports_edge_scanner.connectors.polymarket_auth import (
    PolymarketAuthConfig,
    load_polymarket_auth_config,
)
from sports_edge_scanner.core.execution import (
    LiveModeConfig,
    load_live_mode_config,
)


def _credential_env_names(config: PolymarketAuthConfig) -> list[str]:
    return [
        config.funder_env,
        config.private_key_env,
        config.api_key_env,
        config.api_secret_env,
        config.api_passphrase_env,
    ]


def build_live_status(
    *,
    live_config_path: str | Path,
    auth_config_path: str | Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    env = environ if environ is not None else os.environ
    blockers: list[str] = []
    live_config_loaded = False
    auth_config_loaded = False
    live_config = LiveModeConfig()
    auth_config = PolymarketAuthConfig()

    live_path = Path(live_config_path)
    auth_path = Path(auth_config_path)

    if live_path.exists():
        live_config = load_live_mode_config(live_path)
        live_config_loaded = True
    else:
        blockers.append("live config missing")

    if auth_path.exists():
        auth_config = load_polymarket_auth_config(auth_path)
        auth_config_loaded = True
    else:
        blockers.append("auth config missing")

    if live_config.mode != "live":
        blockers.append("live mode is not live")
    if not live_config.live_enabled:
        blockers.append("live mode disabled")
    if live_config.kill_switch_enabled:
        blockers.append("kill switch enabled")
    if live_config.require_confirmation_token:
        blockers.append("confirmation token required")

    if not auth_config.enabled:
        blockers.append("auth config disabled")
    if not auth_config.allow_live_writes:
        blockers.append("live writes disabled")

    missing_credential_envs = [
        name for name in _credential_env_names(auth_config) if not env.get(name)
    ]
    if missing_credential_envs:
        blockers.append("credential environment missing")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "live_config_loaded": live_config_loaded,
        "auth_config_loaded": auth_config_loaded,
        "mode": live_config.mode,
        "live_enabled": live_config.live_enabled,
        "kill_switch_enabled": live_config.kill_switch_enabled,
        "require_confirmation_token": live_config.require_confirmation_token,
        "auth_enabled": auth_config.enabled,
        "allow_live_writes": auth_config.allow_live_writes,
        "require_geoblock_check": auth_config.require_geoblock_check,
        "credential_status": (
            "missing" if missing_credential_envs else "present"
        ),
        "missing_credential_envs": missing_credential_envs,
    }
