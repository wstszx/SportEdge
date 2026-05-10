import socket
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Protocol


class ProcessResult(Protocol):
    returncode: int


@dataclass(frozen=True)
class AppLaunchConfig:
    dashboard_path: Path = Path("dashboard_app.py")
    host: str = "localhost"
    port: int = 8501
    open_browser: bool = True
    port_scan_attempts: int = 20


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


def launch_app(
    config: AppLaunchConfig,
    run_process: Callable[[list[str]], ProcessResult] = subprocess.run,
    is_port_available: Callable[[str, int], bool] = is_port_available,
) -> int:
    port = resolve_available_port(
        config.host,
        config.port,
        attempts=config.port_scan_attempts,
        is_port_available=is_port_available,
    )
    result = run_process(build_streamlit_command(replace(config, port=port)))
    return int(result.returncode)
