import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sports_edge_scanner.core.events import append_event, make_event


def run_shadow_watch(
    scan_once: Callable[[int], dict[str, Any]],
    build_report: Callable[[], dict[str, Any]],
    events_path: Path,
    iterations: int,
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")

    summaries: list[dict[str, Any]] = []
    failure_count = 0

    for iteration in range(1, iterations + 1):
        try:
            summaries.append(scan_once(iteration))
        except Exception as exc:
            failure_count += 1
            append_event(
                events_path,
                make_event(
                    "shadow_scan_error",
                    str(uuid4()),
                    {
                        "iteration": iteration,
                        "error": str(exc),
                    },
                ),
            )
        if iteration < iterations:
            sleep(interval_seconds)

    report = build_report()
    successful_iterations = iterations - failure_count
    return {
        "completed_iterations": iterations,
        "successful_iterations": successful_iterations,
        "failed_iterations": failure_count,
        "events_path": str(events_path),
        "scan_summaries": summaries,
        "readiness": report.get("readiness", {}),
        "report": report,
    }
