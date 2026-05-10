import json
from dataclasses import asdict
from pathlib import Path

from sports_edge_scanner.core.risk import RiskConfig


def default_risk_config_dict() -> dict[str, float | int]:
    return asdict(RiskConfig())


def default_fair_probability_example() -> dict[str, object]:
    return {
        "markets": {
            "example-market-slug": {
                "Team A": 0.57,
            }
        },
        "tokens": {
            "example-token-id": 0.57,
        },
    }


def _write_json(path: Path, payload: dict[str, object], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_shadow_config_templates(
    config_path: Path,
    fair_path: Path,
    force: bool = False,
) -> list[Path]:
    _write_json(config_path, default_risk_config_dict(), force=force)
    _write_json(fair_path, default_fair_probability_example(), force=force)
    return [config_path, fair_path]
