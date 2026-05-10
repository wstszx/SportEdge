import subprocess
import sys
from dataclasses import dataclass
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
) -> int:
    result = run_process(build_streamlit_command(config))
    return int(result.returncode)
