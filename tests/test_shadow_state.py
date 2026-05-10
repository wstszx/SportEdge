import pytest

from sports_edge_scanner.core.shadow_state import build_shadow_state


def test_build_shadow_state_replays_fills_rejections_and_exposure():
    events = [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {"event_type": "orderbook_error", "market_id": "m2", "token_id": "t2"},
        {
            "event_type": "risk_decision",
            "allowed": False,
            "market_id": "m1",
            "reasons": ["wide spread", "low liquidity"],
        },
        {
            "event_type": "risk_decision",
            "allowed": True,
            "market_id": "m1",
            "token_id": "t1",
            "approved_notional": 10.0,
            "reasons": ["allowed"],
        },
        {
            "event_type": "shadow_fill",
            "market_id": "m1",
            "outcome_name": "Team A",
            "token_id": "t1",
            "status": "partial",
            "filled_notional": 6.0,
            "unfilled_notional": 4.0,
            "slippage": 0.02,
        },
    ]

    state = build_shadow_state(events)

    assert state["candidate_count"] == 1
    assert state["accepted_order_count"] == 1
    assert state["rejected_order_count"] == 1
    assert state["orderbook_error_count"] == 1
    assert state["simulated_notional_filled"] == 6.0
    assert state["simulated_unfilled_notional"] == 4.0
    assert state["average_slippage"] == pytest.approx(0.02)
    assert state["rejections_by_reason"] == {"wide spread": 1, "low liquidity": 1}
    assert state["exposure_by_market"] == {"m1": 6.0}
    assert state["exposure_by_outcome"] == {"m1:Team A": 6.0}
    assert state["fill_status_counts"] == {"partial": 1}
    assert state["fills"][0]["outcome_name"] == "Team A"


def test_build_shadow_state_counts_distinct_run_ids():
    events = [
        {"event_type": "model_estimate", "run_id": "run-2", "usable": True},
        {"event_type": "signal", "run_id": "run-1", "status": "candidate"},
        {"event_type": "shadow_fill", "run_id": "run-1", "status": "full"},
        {"event_type": "orderbook_error", "run_id": ""},
        {"event_type": "risk_decision"},
    ]

    state = build_shadow_state(events)

    assert state["run_count"] == 2
    assert state["run_ids"] == ["run-1", "run-2"]
