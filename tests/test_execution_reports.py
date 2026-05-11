from sports_edge_scanner.core.execution_reports import build_execution_report


def test_execution_report_is_empty_without_events():
    report = build_execution_report([])

    assert report["run_count"] == 0
    assert report["intent_count"] == 0
    assert report["submitted_order_count"] == 0
    assert report["rejected_order_count"] == 0
    assert report["latest_status"] is None
    assert report["orders"] == []


def test_execution_report_summarizes_submissions_and_rejections():
    events = [
        {
            "event_type": "execution_intent",
            "timestamp": "2026-05-10T00:00:00+00:00",
            "run_id": "run-1",
            "client_order_id": "client-1",
            "market_id": "market-1",
            "market_slug": "team-a-team-b",
            "outcome_name": "Team A",
            "token_id": "token-a",
            "side": "BUY",
            "order_type": "LIMIT",
            "limit_price": 0.52,
            "notional": 10.0,
            "time_in_force": "IOC",
        },
        {
            "event_type": "live_guard_decision",
            "timestamp": "2026-05-10T00:00:01+00:00",
            "run_id": "run-1",
            "allowed": True,
            "reasons": ["allowed live execution"],
            "mode": "live",
            "requested_notional": 10.0,
            "approved_notional": 10.0,
        },
        {
            "event_type": "execution_order",
            "timestamp": "2026-05-10T00:00:02+00:00",
            "run_id": "run-1",
            "client_order_id": "client-1",
            "venue_order_id": "venue-1",
            "status": "submitted",
            "filled_notional": 2.0,
            "remaining_notional": 8.0,
            "average_price": 0.52,
            "message": "submitted",
        },
        {
            "event_type": "execution_result",
            "timestamp": "2026-05-10T00:00:03+00:00",
            "run_id": "run-1",
            "client_order_id": "client-1",
            "venue_order_id": "venue-1",
            "status": "submitted",
            "filled_notional": 2.0,
            "remaining_notional": 8.0,
            "average_price": 0.52,
            "message": "submitted",
        },
        {
            "event_type": "execution_intent",
            "timestamp": "2026-05-10T00:01:00+00:00",
            "run_id": "run-2",
            "client_order_id": "client-2",
            "market_id": "market-2",
            "market_slug": "team-c-team-d",
            "outcome_name": "Team C",
            "token_id": "token-c",
            "side": "BUY",
            "order_type": "LIMIT",
            "limit_price": 0.49,
            "notional": 5.0,
            "time_in_force": "IOC",
        },
        {
            "event_type": "live_guard_decision",
            "timestamp": "2026-05-10T00:01:01+00:00",
            "run_id": "run-2",
            "allowed": False,
            "reasons": ["kill switch enabled"],
            "mode": "live",
            "requested_notional": 5.0,
            "approved_notional": 0.0,
        },
        {
            "event_type": "execution_rejected",
            "timestamp": "2026-05-10T00:01:02+00:00",
            "run_id": "run-2",
            "client_order_id": "client-2",
            "venue_order_id": "",
            "status": "rejected",
            "filled_notional": 0.0,
            "remaining_notional": 5.0,
            "average_price": None,
            "message": "kill switch enabled",
        },
    ]

    report = build_execution_report(events)

    assert report["run_count"] == 2
    assert report["intent_count"] == 2
    assert report["guard_allowed_count"] == 1
    assert report["guard_rejected_count"] == 1
    assert report["submitted_order_count"] == 1
    assert report["rejected_order_count"] == 1
    assert report["terminal_event_count"] == 2
    assert report["filled_notional"] == 2.0
    assert report["remaining_notional"] == 13.0
    assert report["latest_status"] == "rejected"
    assert report["status_counts"] == {"rejected": 1, "submitted": 1}
    assert report["guard_rejections_by_reason"] == {"kill switch enabled": 1}
    assert report["orders"][0]["client_order_id"] == "client-1"
    assert report["orders"][0]["guard_allowed"] is True
    assert report["orders"][0]["status"] == "submitted"
    assert report["orders"][1]["guard_reasons"] == ["kill switch enabled"]


def test_execution_report_counts_execution_client_failure_statuses_as_rejections():
    report = build_execution_report(
        [
            {
                "event_type": "execution_order",
                "timestamp": "2026-05-10T00:00:00+00:00",
                "run_id": "run-1",
                "client_order_id": "client-1",
                "venue_order_id": "",
                "status": "sdk_error",
                "filled_notional": 0.0,
                "remaining_notional": 10.0,
                "average_price": None,
                "message": "sdk_error",
            },
            {
                "event_type": "execution_result",
                "timestamp": "2026-05-10T00:00:01+00:00",
                "run_id": "run-1",
                "client_order_id": "client-1",
                "venue_order_id": "",
                "status": "sdk_error",
                "filled_notional": 0.0,
                "remaining_notional": 10.0,
                "average_price": None,
                "message": "sdk_error",
            },
        ]
    )

    assert report["submitted_order_count"] == 0
    assert report["rejected_order_count"] == 1
    assert report["latest_status"] == "sdk_error"
    assert report["orders"][0]["timestamp"] == "2026-05-10T00:00:00+00:00"
