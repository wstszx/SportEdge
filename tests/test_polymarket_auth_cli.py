from sports_edge_scanner.cli import build_parser, main


def test_parser_supports_polymarket_auth_readiness_commands():
    parser = build_parser()

    init_args = parser.parse_args(["polymarket-auth", "init-config", "--config", "auth.json"])
    check_args = parser.parse_args(["polymarket-auth", "check", "--config", "auth.json"])
    geo_args = parser.parse_args(["polymarket-auth", "geoblock", "--json"])

    assert init_args.command == "polymarket-auth"
    assert init_args.polymarket_auth_command == "init-config"
    assert check_args.polymarket_auth_command == "check"
    assert geo_args.polymarket_auth_command == "geoblock"


def test_parser_does_not_expose_real_order_command():
    parser = build_parser()

    choices = parser._subparsers._actions[1].choices[
        "polymarket-auth"
    ]._subparsers._actions[1].choices

    assert "place-order" not in choices
    assert "trade" not in choices
    assert "cancel-order" not in choices


def test_polymarket_auth_init_and_check_commands(tmp_path):
    config_path = tmp_path / "polymarket_auth_config.json"

    assert main(["polymarket-auth", "init-config", "--config", str(config_path)]) == 0
    assert main(["polymarket-auth", "check", "--config", str(config_path)]) == 1
