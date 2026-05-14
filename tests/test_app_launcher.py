import sys
import subprocess
from pathlib import Path

from sports_edge_scanner.core.app_launcher import (
    AppLaunchConfig,
    build_monitor_command,
    build_streamlit_command,
    resolve_available_port,
    launch_app,
    stop_process,
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


def test_build_monitor_command_runs_continuous_paper_mode_by_default():
    command = build_monitor_command(
        AppLaunchConfig(
            auto_monitor=True,
            monitor_limit=12,
            monitor_interval_seconds=60.0,
            snapshot_path=Path("snapshots.jsonl"),
            shadow_events_path=Path("shadow.jsonl"),
        )
    )

    assert command[:3] == [sys.executable, "-m", "sports_edge_scanner"]
    assert command[3:5] == ["monitor", "paper"]
    assert "--limit=12" in command
    assert "--interval-seconds=60.0" in command
    assert "--snapshots=snapshots.jsonl" in command
    assert "--events=shadow.jsonl" in command


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


def test_launch_app_starts_background_monitor_before_streamlit():
    run_calls = []
    started = []

    class Result:
        returncode = 0

    class Process:
        pid = 1234

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    def run_process(command):
        run_calls.append(command)
        return Result()

    def start_process(command):
        started.append(command)
        return Process()

    exit_code = launch_app(
        AppLaunchConfig(auto_monitor=True),
        run_process=run_process,
        start_process=start_process,
        is_port_available=lambda host, port: True,
    )

    assert exit_code == 0
    assert started[0][3:5] == ["monitor", "paper"]
    assert run_calls[0][:4] == [sys.executable, "-m", "streamlit", "run"]


def test_launch_app_stops_background_monitor_after_streamlit_exits():
    stopped = []

    class Result:
        returncode = 0

    class Process:
        pid = 1234

        def terminate(self):
            stopped.append("terminate")

        def wait(self, timeout=None):
            stopped.append(("wait", timeout))

    exit_code = launch_app(
        AppLaunchConfig(auto_monitor=True),
        run_process=lambda command: Result(),
        start_process=lambda command: Process(),
        is_port_available=lambda host, port: True,
    )

    assert exit_code == 0
    assert stopped == ["terminate", ("wait", 5)]


def test_stop_process_kills_monitor_when_terminate_times_out():
    calls = []

    class Process:
        wait_calls = 0

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            self.wait_calls += 1
            calls.append(("wait", timeout))
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("monitor", timeout)

        def kill(self):
            calls.append("kill")

    stop_process(Process(), timeout=2)

    assert calls == ["terminate", ("wait", 2), "kill", ("wait", 2)]


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
