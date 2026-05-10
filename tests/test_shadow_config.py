import json

import pytest

from sports_edge_scanner.core.shadow_config import (
    default_fair_probability_example,
    default_risk_config_dict,
    write_shadow_config_templates,
)


def test_default_risk_config_dict_matches_safe_defaults():
    config = default_risk_config_dict()

    assert config["max_order_notional"] == 10.0
    assert config["max_total_exposure"] == 100.0
    assert config["stale_book_seconds"] == 30


def test_write_shadow_config_templates_refuses_overwrite_without_force(tmp_path):
    config_path = tmp_path / "shadow_config.json"
    fair_path = tmp_path / "fair_probabilities.example.json"
    config_path.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_shadow_config_templates(config_path, fair_path, force=False)


def test_write_shadow_config_templates_writes_files(tmp_path):
    config_path = tmp_path / "shadow_config.json"
    fair_path = tmp_path / "fair_probabilities.example.json"

    written = write_shadow_config_templates(config_path, fair_path, force=False)

    assert written == [config_path, fair_path]
    assert json.loads(config_path.read_text(encoding="utf-8"))["max_order_notional"] == 10.0
    assert json.loads(fair_path.read_text(encoding="utf-8")) == default_fair_probability_example()
