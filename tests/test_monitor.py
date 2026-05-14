from sports_edge_scanner.core.monitor import run_paper_monitor


def test_run_paper_monitor_repeats_snapshot_and_shadow_scan():
    calls = []

    def collect_once():
        calls.append("snapshot")
        return 3

    def scan_once():
        calls.append("shadow")
        return {"candidate_count": 0}

    result = run_paper_monitor(
        collect_once=collect_once,
        scan_once=scan_once,
        iterations=2,
        interval_seconds=0.0,
    )

    assert calls == ["snapshot", "shadow", "snapshot", "shadow"]
    assert result == {
        "completed_iterations": 2,
        "failed_iterations": 0,
        "snapshot_counts": [3, 3],
        "scan_summaries": [{"candidate_count": 0}, {"candidate_count": 0}],
        "errors": [],
    }


def test_run_paper_monitor_continues_after_iteration_failure():
    calls = []

    def collect_once():
        calls.append("snapshot")
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        return 1

    def scan_once():
        calls.append("shadow")
        return {"candidate_count": 0}

    result = run_paper_monitor(
        collect_once=collect_once,
        scan_once=scan_once,
        iterations=2,
        interval_seconds=0.0,
    )

    assert calls == ["snapshot", "snapshot", "shadow"]
    assert result["completed_iterations"] == 2
    assert result["failed_iterations"] == 1
    assert result["snapshot_counts"] == [1]
    assert result["errors"][0]["error"] == "temporary failure"


def test_run_paper_monitor_reports_iteration_failure_to_callback():
    errors = []

    def collect_once():
        raise RuntimeError("temporary failure")

    def scan_once():
        return {"candidate_count": 0}

    result = run_paper_monitor(
        collect_once=collect_once,
        scan_once=scan_once,
        iterations=1,
        interval_seconds=0.0,
        on_error=errors.append,
    )

    assert result["failed_iterations"] == 1
    assert errors == [{"iteration": 1, "error": "temporary failure"}]
