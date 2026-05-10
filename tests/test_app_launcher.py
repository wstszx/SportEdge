import sys
from pathlib import Path

from sports_edge_scanner.core.app_launcher import (
    AppLaunchConfig,
    build_streamlit_command,
    resolve_available_port,
    launch_app,
)


def test_build_streamlit_command_includes_dashboard_host_port_and_browser_flag():
    command = build_streamlit_command(
        AppLaunchConfig(
            dashboard_path=Path("dashboard_app.py"),
            host="127.0.0.1",
            port=8502,
            open_browser=False,
        )
    )

    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert command[4] == "dashboard_app.py"
    assert "--server.address=127.0.0.1" in command
    assert "--server.port=8502" in command
    assert "--server.headless=true" in command


def test_resolve_available_port_keeps_free_requested_port():
    assert (
        resolve_available_port(
            "localhost",
            8501,
            is_port_available=lambda host, port: port == 8501,
        )
        == 8501
    )


def test_resolve_available_port_uses_next_port_when_requested_port_is_busy():
    checked = []

    def is_port_available(host, port):
        checked.append((host, port))
        return port == 8503

    assert resolve_available_port("localhost", 8501, is_port_available=is_port_available) == 8503
    assert checked == [
        ("localhost", 8501),
        ("localhost", 8502),
        ("localhost", 8503),
    ]


def test_launch_app_uses_available_port_for_streamlit_command():
    calls = []

    class Result:
        returncode = 0

    def run_process(command):
        calls.append(command)
        return Result()

    exit_code = launch_app(
        AppLaunchConfig(port=8501),
        run_process=run_process,
        is_port_available=lambda host, port: port == 8502,
    )

    assert exit_code == 0
    assert "--server.port=8502" in calls[0]


def test_launch_app_uses_injected_process_runner():
    calls = []

    class Result:
        returncode = 7

    def run_process(command):
        calls.append(command)
        return Result()

    exit_code = launch_app(
        AppLaunchConfig(
            dashboard_path=Path("dashboard_app.py"),
            host="localhost",
            port=8501,
        ),
        run_process=run_process,
    )

    assert exit_code == 7
    assert calls
    assert calls[0][:4] == [sys.executable, "-m", "streamlit", "run"]
