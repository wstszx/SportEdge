import pytest

from sports_edge_scanner.core.strategy_funnel import build_strategy_funnel_diagnostics


def orderbook_event(token_id, best_bid, best_ask):
    return {
        "event_type": "orderbook_snapshot",
        "run_id": "run-1",
        "token_id": token_id,
        "bids": [{"price": best_bid, "size": 100.0}],
        "asks": [{"price": best_ask, "size": 100.0}],
    }


def estimate_event(token_id, probability, usable=True, reasons=None):
    return {
        "event_type": "model_estimate",
        "run_id": "run-1",
        "token_id": token_id,
        "market_id": "m1",
        "market_slug": "market-1",
        "outcome_name": token_id,
        "probability": probability,
        "usable": usable,
        "reasons": reasons or ["usable automatic estimate"],
        "source": "orderbook_midpoint",
        "confidence": 1.0,
    }


def test_strategy_funnel_reports_min_edge_sensitivity_from_event_log():
    diagnostics = build_strategy_funnel_diagnostics(
        [
            orderbook_event("t1", best_bid=0.50, best_ask=0.52),
            estimate_event("t1", probability=0.55),
            orderbook_event("t2", best_bid=0.40, best_ask=0.41),
            estimate_event("t2", probability=0.415),
            estimate_event("t3", probability=0.70, usable=False, reasons=["wide spread"]),
        ],
        min_edges=[0.03, 0.02, 0.01],
    )

    assert diagnostics["model_estimate_count"] == 3
    assert diagnostics["usable_model_estimate_count"] == 2
    assert diagnostics["estimates_with_orderbook_count"] == 2
    assert diagnostics["min_edge_sensitivity"] == [
        {"min_edge": 0.03, "candidate_count": 1},
        {"min_edge": 0.02, "candidate_count": 1},
        {"min_edge": 0.01, "candidate_count": 1},
    ]
    assert diagnostics["edge_summary"]["max"] == pytest.approx(0.03)
    assert diagnostics["top_candidate_gaps"][0]["token_id"] == "t1"


def test_strategy_funnel_explains_when_auto_fair_self_cancels():
    diagnostics = build_strategy_funnel_diagnostics(
        [
            orderbook_event("t1", best_bid=0.48, best_ask=0.52),
            estimate_event("t1", probability=0.50),
        ],
        min_edges=[0.03, 0.02, 0.01],
    )

    assert diagnostics["min_edge_sensitivity"] == [
        {"min_edge": 0.03, "candidate_count": 0},
        {"min_edge": 0.02, "candidate_count": 0},
        {"min_edge": 0.01, "candidate_count": 0},
    ]
    assert diagnostics["primary_blockers"] == [
        "usable estimates do not clear executable ask prices"
    ]


def test_strategy_funnel_does_not_mix_orderbooks_across_runs():
    diagnostics = build_strategy_funnel_diagnostics(
        [
            {
                **orderbook_event("t1", best_bid=0.48, best_ask=0.52),
                "run_id": "run-1",
            },
            {
                **estimate_event("t1", probability=0.50),
                "run_id": "run-1",
            },
            {
                **orderbook_event("t1", best_bid=0.10, best_ask=0.12),
                "run_id": "run-2",
            },
        ],
        min_edges=[0.03],
    )

    assert diagnostics["min_edge_sensitivity"] == [
        {"min_edge": 0.03, "candidate_count": 0}
    ]


def test_strategy_funnel_top_gaps_are_deduplicated_by_token():
    diagnostics = build_strategy_funnel_diagnostics(
        [
            {
                **orderbook_event("t1", best_bid=0.98, best_ask=0.99),
                "run_id": "run-1",
            },
            {
                **estimate_event("t1", probability=0.985),
                "run_id": "run-1",
            },
            {
                **orderbook_event("t1", best_bid=0.98, best_ask=0.99),
                "run_id": "run-2",
            },
            {
                **estimate_event("t1", probability=0.985),
                "run_id": "run-2",
            },
        ],
    )

    assert len(diagnostics["top_candidate_gaps"]) == 1
