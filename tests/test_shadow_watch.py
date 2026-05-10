import json

import pytest

from sports_edge_scanner.core.shadow_watch import run_shadow_watch


def test_run_shadow_watch_runs_iterations_and_sleeps_between_runs(tmp_path):
    calls = []
    sleeps = []

    def scan_once(iteration):
        calls.append(iteration)
        return {"iteration": iteration}

    result = run_shadow_watch(
        scan_once=scan_once,
        build_report=lambda: {"readiness": {"ready": False, "blockers": []}},
        events_path=tmp_path / "shadow_events.jsonl",
        iterations=3,
        interval_seconds=5.0,
        sleep=sleeps.append,
    )

    assert calls == [1, 2, 3]
    assert sleeps == [5.0, 5.0]
    assert result["completed_iterations"] == 3
    assert result["successful_iterations"] == 3
    assert result["failed_iterations"] == 0


def test_run_shadow_watch_rejects_invalid_inputs(tmp_path):
    with pytest.raises(ValueError, match="iterations"):
        run_shadow_watch(
            scan_once=lambda iteration: {},
            build_report=lambda: {},
            events_path=tmp_path / "events.jsonl",
            iterations=0,
            interval_seconds=1.0,
            sleep=lambda seconds: None,
        )

    with pytest.raises(ValueError, match="interval_seconds"):
        run_shadow_watch(
            scan_once=lambda iteration: {},
            build_report=lambda: {},
            events_path=tmp_path / "events.jsonl",
            iterations=1,
            interval_seconds=-1.0,
            sleep=lambda seconds: None,
        )


def test_run_shadow_watch_continues_after_failure_and_logs_event(tmp_path):
    events_path = tmp_path / "shadow_events.jsonl"
    calls = []

    def scan_once(iteration):
        calls.append(iteration)
        if iteration == 1:
            raise RuntimeError("temporary data outage")
        return {"markets": 1}

    result = run_shadow_watch(
        scan_once=scan_once,
        build_report=lambda: {"readiness": {"ready": False, "blockers": []}},
        events_path=events_path,
        iterations=2,
        interval_seconds=0.0,
        sleep=lambda seconds: None,
    )

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]

    assert calls == [1, 2]
    assert result["successful_iterations"] == 1
    assert result["failed_iterations"] == 1
    assert events[0]["event_type"] == "shadow_scan_error"
    assert events[0]["iteration"] == 1
    assert events[0]["error"] == "temporary data outage"
