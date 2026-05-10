from sports_edge_scanner.core.events import append_event, make_event, read_events


def test_make_event_adds_schema_run_and_timestamp():
    event = make_event(
        "signal",
        run_id="run-1",
        payload={"market_id": "m1", "status": "candidate"},
        timestamp="2026-05-10T00:00:00+00:00",
    )

    assert event["schema_version"] == 1
    assert event["event_type"] == "signal"
    assert event["run_id"] == "run-1"
    assert event["market_id"] == "m1"


def test_append_and_read_events_round_trip(tmp_path):
    path = tmp_path / "shadow_events.jsonl"
    event = make_event(
        "shadow_fill",
        run_id="run-1",
        payload={"order_id": "shadow-1"},
        timestamp="2026-05-10T00:00:00+00:00",
    )

    append_event(path, event)

    assert read_events(path) == [event]
