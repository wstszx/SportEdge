import socket
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Protocol


class ProcessResult(Protocol):
    returncode: int


@dataclass(frozen=True)
class AppLaunchConfig:
    dashboard_path: Path = Path("dashboard_app.py")
    host: str = "localhost"
    port: int = 8501
    open_browser: bool = True
    port_scan_attempts: int = 20
    auto_monitor: bool = True
    monitor_limit: int = 20
    monitor_interval_seconds: float = 300.0
    snapshot_path: Path = Path("market_snapshots.jsonl")
    shadow_events_path: Path = Path("shadow_events.jsonl")


def is_port_available(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return False
    except OSError:
        return True


def resolve_available_port(
    host: str,
    requested_port: int,
    *,
    attempts: int = 20,
    is_port_available: Callable[[str, int], bool] = is_port_available,
) -> int:
    for offset in range(attempts):
        port = requested_port + offset
        if is_port_available(host, port):
            return port
    raise RuntimeError(
        f"No available port found from {requested_port} to {requested_port + attempts - 1}."
    )


def build_streamlit_command(config: AppLaunchConfig) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(config.dashboard_path),
        f"--server.address={config.host}",
        f"--server.port={config.port}",
        f"--server.headless={'false' if config.open_browser else 'true'}",
    ]


def build_monitor_command(config: AppLaunchConfig) -> list[str]:
    return [
        sys.executable,
        "-m",
        "sports_edge_scanner",
        "monitor",
        "paper",
        f"--limit={config.monitor_limit}",
        f"--interval-seconds={config.monitor_interval_seconds}",
        f"--snapshots={config.snapshot_path}",
        f"--events={config.shadow_events_path}",
    ]


def stop_process(process: Any, timeout: float = 5) -> None:
    terminate = getattr(process, "terminate", None)
    if callable(terminate):
        terminate()
    wait = getattr(process, "wait", None)
    if callable(wait):
        try:
            wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill = getattr(process, "kill", None)
            if callable(kill):
                kill()
                wait(timeout=timeout)


def launch_app(
    config: AppLaunchConfig,
    run_process: Callable[[list[str]], ProcessResult] = subprocess.run,
    start_process: Callable[[list[str]], object] = subprocess.Popen,
    is_port_available: Callable[[str, int], bool] = is_port_available,
) -> int:
    port = resolve_available_port(
        config.host,
        config.port,
        attempts=config.port_scan_attempts,
        is_port_available=is_port_available,
    )
    monitor_process = None
    if config.auto_monitor:
        monitor_process = start_process(build_monitor_command(config))
    try:
        result = run_process(build_streamlit_command(replace(config, port=port)))
        return int(result.returncode)
    finally:
        if monitor_process is not None:
            stop_process(monitor_process)
