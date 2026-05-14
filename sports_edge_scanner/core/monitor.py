import time
from typing import Callable


def run_paper_monitor(
    *,
    collect_once: Callable[[], int],
    scan_once: Callable[[], dict[str, object]],
    iterations: int | None,
    interval_seconds: float,
    on_error: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    completed_iterations = 0
    failed_iterations = 0
    snapshot_counts: list[int] = []
    scan_summaries: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []

    while iterations is None or completed_iterations < iterations:
        try:
            snapshot_counts.append(collect_once())
            scan_summaries.append(scan_once())
        except Exception as exc:
            failed_iterations += 1
            error = {
                "iteration": completed_iterations + 1,
                "error": str(exc),
            }
            errors.append(error)
            if on_error is not None:
                on_error(error)
        completed_iterations += 1
        if iterations is None or completed_iterations < iterations:
            time.sleep(interval_seconds)

    return {
        "completed_iterations": completed_iterations,
        "failed_iterations": failed_iterations,
        "snapshot_counts": snapshot_counts,
        "scan_summaries": scan_summaries,
        "errors": errors,
    }
