import pytest
from pathlib import Path

from dashboard_app import (
    RUN_MODE_LIVE,
    RUN_MODE_PAPER,
    RUN_MODE_PAPER_AND_LIVE,
    UI_TEXT,
    build_live_run_args,
    _label,
    _localize_json,
    _translate_value,
    build_shadow_watch_args,
    build_snapshot_collect_args,
    run_dashboard_mode,
    run_dashboard_shadow_watch,
)
from sports_edge_scanner.dashboard_data import (
    build_dashboard_state,
    latest_market_rows,
    price_history_for_market,
)


def sample_snapshots():
    return [
        {
            "timestamp": "2026-05-09T00:00:00+00:00",
            "market_id": "m1",
            "title": "Market 1",
            "slug": "market-1",
            "liquidity": 1000.0,
            "volume": 2000.0,
            "yes_price": 0.47,
            "no_price": 0.53,
            "signal_status": "watch",
            "signal_reasons": ["no fair probability supplied"],
        },
        {
            "timestamp": "2026-05-09T01:00:00+00:00",
            "market_id": "m1",
            "title": "Market 1",
            "slug": "market-1",
            "liquidity": 1200.0,
            "volume": 2400.0,
            "yes_price": 0.51,
            "no_price": 0.49,
            "signal_status": "candidate",
            "signal_reasons": ["fair probability clears edge threshold"],
        },
        {
            "timestamp": "2026-05-09T00:30:00+00:00",
            "market_id": "m2",
            "title": "Market 2",
            "slug": "market-2",
            "liquidity": 50.0,
            "volume": 80.0,
            "yes_price": None,
            "no_price": None,
            "signal_status": "watch",
            "signal_reasons": ["missing YES or NO price"],
        },
    ]


def sample_records():
    return [
        {
            "type": "trade",
            "timestamp": "2026-05-09T00:05:00+00:00",
            "market": "m1",
            "side": "YES",
            "price": 0.47,
            "size": 100.0,
            "note": "tracking",
            "metadata": {"market_id": "m1"},
        },
        {
            "type": "settlement",
            "timestamp": "2026-05-10T00:00:00+00:00",
            "market": "m1",
            "market_id": "m1",
            "winning_side": "YES",
            "note": "resolved",
        },
    ]


def sample_shadow_events():
    return [
        {"event_type": "signal", "status": "candidate", "market_id": "m1"},
        {
            "event_type": "risk_decision",
            "market_id": "m1",
            "allowed": False,
            "reasons": ["wide spread"],
        },
        {
            "event_type": "shadow_fill",
            "market_id": "m1",
            "outcome_name": "Team A",
            "token_id": "token-a",
            "status": "partial",
            "filled_notional": 5.0,
            "unfilled_notional": 3.0,
            "slippage": 0.02,
        },
    ]


def test_latest_market_rows_returns_latest_snapshot_per_market_sorted_by_signal():
    rows = latest_market_rows(sample_snapshots())

    assert rows[0]["market_id"] == "m1"
    assert rows[0]["yes_price"] == 0.51
    assert rows[0]["signal_status"] == "candidate"
    assert rows[1]["market_id"] == "m2"


def test_price_history_for_market_returns_chronological_rows():
    rows = price_history_for_market(sample_snapshots(), "m1")

    assert [row["yes_price"] for row in rows] == [0.47, 0.51]
    assert rows[0]["timestamp"] < rows[1]["timestamp"]


def test_build_dashboard_state_combines_reports_quality_and_tables():
    state = build_dashboard_state(sample_records(), sample_snapshots())

    assert state["report"]["paper_trades"] == 1
    assert state["report"]["realized_pnl"] == pytest.approx(112.7659574468)
    assert state["quality"]["market_count"] == 2
    assert len(state["latest_markets"]) == 2
    assert len(state["paper_trades"]) == 1
    assert len(state["settlements"]) == 1


def test_build_dashboard_state_includes_shadow_report_and_tables():
    state = build_dashboard_state(
        sample_records(),
        sample_snapshots(),
        sample_shadow_events(),
    )

    assert state["shadow_report"]["candidate_count"] == 1
    assert state["shadow_report"]["simulated_unfilled_notional"] == 3.0
    assert state["shadow_exposure_by_market"] == [
        {"market_id": "m1", "exposure": 5.0}
    ]
    assert state["shadow_exposure_by_outcome"] == [
        {"market_outcome": "m1:Team A", "exposure": 5.0}
    ]
    assert state["shadow_risk_decisions"][0]["reasons"] == ["wide spread"]
    assert state["shadow_fills"][0]["outcome_name"] == "Team A"


def test_dashboard_ui_text_is_localized_to_chinese():
    assert UI_TEXT["app_title"] == "体育下注研究仪表盘"
    assert UI_TEXT["sidebar_help"] == "数据会在启动所选运行模式时自动采集；这些路径通常保持默认即可。"
    assert _label("realized_pnl") == "已结算盈亏"
    assert _label("realized_roi") == "已结算收益率"
    assert _label("average_clv") == "平均收盘价优势"
    assert _label("markets_tab") == "市场"
    assert _label("paper_trades_tab") == "模拟交易"
    assert _label("quality_tab") == "数据质量"


def test_dashboard_has_shadow_ui_labels():
    assert _label("shadow_tab") == "影子交易"
    assert _label("shadow_events_path") == "影子事件文件"
    assert _label("shadow_quality_clean") == "影子交易数据质量当前无警告。"


def test_dashboard_has_control_ui_labels():
    assert _label("control_tab") == "控制台"
    assert _label("shadow_controls") == "运行模式控制"
    assert _label("start_selected_run_mode") == "启动所选模式"
    assert _label("live_safety_status") == "实盘安全状态"
    assert "复用纸面交易" in _label("live_safety_message")


def test_dashboard_has_operator_run_mode_labels():
    assert _label("run_mode") == "运行模式"
    assert _label("run_mode_paper") == "仅纸面"
    assert _label("run_mode_live") == "仅实盘"
    assert _label("run_mode_paper_and_live") == "纸面+实盘"
    assert _label("start_selected_run_mode") == "启动所选模式"
    assert _label("automatic_data_fetch") == "自动采集数据"
    assert _label("advanced_settings") == "高级设置"
    assert _label("polymarket_auth_config_path") == "Polymarket 实盘配置文件"


def test_dashboard_keeps_data_and_collection_settings_advanced():
    source = Path("dashboard_app.py").read_text(encoding="utf-8")

    assert 'st.expander(_label("advanced_settings"), expanded=False)' in source
    assert 'st.sidebar.expander(_label("advanced_settings"), expanded=False)' in source


def test_dashboard_has_strategy_diagnostics_labels():
    assert _label("strategy_diagnostics") == "策略诊断"
    assert _label("diagnostic_issues") == "诊断问题"
    assert _label("diagnostic_next_actions") == "下一步建议"
    assert _translate_value("needs_independent_signal") == "需要独立信号"
    assert _translate_value("add independent signal source") == "接入独立信号来源"


def test_dashboard_uses_current_streamlit_width_api():
    source = Path("dashboard_app.py").read_text(encoding="utf-8")

    assert "use_container_width" not in source
    assert 'width="stretch"' in source


def test_dashboard_translates_status_reasons_sides_and_json_keys():
    assert _translate_value("candidate") == "候选"
    assert _translate_value("watch") == "观察"
    assert _translate_value("YES") == "是"
    assert _translate_value("no fair probability supplied") == "未提供公平概率"
    assert _translate_value("shadow scan errors present") == "存在影子扫描错误"
    assert _translate_value(None) == "无数据"

    localized = _localize_json(
        {
            "realized_pnl": 12.5,
            "trades": [
                {
                    "side": "YES",
                    "signal_status": "candidate",
                    "signal_reasons": "fair probability clears edge threshold",
                }
            ],
        }
    )

    assert "已结算盈亏" in localized
    assert "已结算收益率" not in localized
    assert localized["交易"][0]["方向"] == "是"
    assert localized["交易"][0]["信号状态"] == "候选"
    assert localized["交易"][0]["信号原因"] == "公平概率超过优势阈值"
    assert _localize_json({"markets": []}) == {"市场列表": []}


def test_build_shadow_watch_args_maps_ui_values():
    args = build_shadow_watch_args(
        limit=5,
        iterations=3,
        interval_seconds=0.0,
        config_path="shadow_config.json",
        events_path="shadow_events.jsonl",
        auto_fair_min_confidence=0.8,
    )

    assert args.shadow_command == "watch"
    assert args.limit == 5
    assert args.iterations == 3
    assert args.interval_seconds == 0.0
    assert args.config == "shadow_config.json"
    assert args.events == "shadow_events.jsonl"
    assert args.auto_fair_min_confidence == 0.8
    assert args.fair == ""
    assert args.json is True


def test_build_snapshot_collect_args_maps_automatic_data_values():
    args = build_snapshot_collect_args(
        limit=12,
        snapshot_path="market_snapshots.jsonl",
    )

    assert args.limit == 12
    assert args.snapshots == "market_snapshots.jsonl"
    assert args.fair == []


def test_build_live_run_args_maps_ui_values():
    args = build_live_run_args(
        live_config_path="live_config.json",
        auth_config_path="polymarket_auth_config.json",
        events_path="execution_events.jsonl",
        limit=5,
        auto_fair_min_confidence=0.8,
    )

    assert args.live_command == "run"
    assert args.live_config == "live_config.json"
    assert args.auth_config == "polymarket_auth_config.json"
    assert args.events == "execution_events.jsonl"
    assert args.limit == 5
    assert args.auto_fair_min_confidence == 0.8
    assert args.json is True


def test_run_dashboard_shadow_watch_uses_injected_runner():
    calls = []

    def runner(args):
        calls.append(args)
        return 0

    exit_code = run_dashboard_shadow_watch(
        limit=2,
        iterations=1,
        interval_seconds=0.0,
        config_path="shadow_config.json",
        events_path="shadow_events.jsonl",
        auto_fair_min_confidence=0.75,
        runner=runner,
    )

    assert exit_code == 0
    assert calls[0].limit == 2


def test_run_dashboard_mode_paper_fetches_data_then_runs_paper_only():
    calls = []

    def snapshot_runner(args):
        calls.append(("snapshot", args.snapshots))
        return 0

    def shadow_runner(args):
        calls.append(("paper", args.events))
        return 0

    def live_runner(args):
        calls.append(("live", args.events))
        return 0

    result = run_dashboard_mode(
        mode=RUN_MODE_PAPER,
        snapshot_path="market_snapshots.jsonl",
        shadow_events_path="shadow_events.jsonl",
        execution_events_path="execution_events.jsonl",
        snapshot_runner=snapshot_runner,
        shadow_runner=shadow_runner,
        live_runner=live_runner,
    )

    assert result["success"] is True
    assert calls == [
        ("snapshot", "market_snapshots.jsonl"),
        ("paper", "shadow_events.jsonl"),
    ]
    assert result["paper_exit_code"] == 0
    assert result["live_exit_code"] is None


def test_run_dashboard_mode_live_fetches_data_then_runs_live_only():
    calls = []

    def snapshot_runner(args):
        calls.append(("snapshot", args.snapshots))
        return 0

    def shadow_runner(args):
        calls.append(("paper", args.events))
        return 0

    def live_runner(args):
        calls.append(("live", args.events))
        return 0

    result = run_dashboard_mode(
        mode=RUN_MODE_LIVE,
        snapshot_path="market_snapshots.jsonl",
        shadow_events_path="shadow_events.jsonl",
        execution_events_path="execution_events.jsonl",
        snapshot_runner=snapshot_runner,
        shadow_runner=shadow_runner,
        live_runner=live_runner,
    )

    assert result["success"] is True
    assert calls == [
        ("snapshot", "market_snapshots.jsonl"),
        ("live", "execution_events.jsonl"),
    ]
    assert result["paper_exit_code"] is None
    assert result["live_exit_code"] == 0


def test_run_dashboard_mode_combined_fetches_data_then_runs_paper_and_live():
    calls = []

    def snapshot_runner(args):
        calls.append(("snapshot", args.snapshots))
        return 0

    def shadow_runner(args):
        calls.append(("paper", args.events))
        return 0

    def live_runner(args):
        calls.append(("live", args.events))
        return 0

    result = run_dashboard_mode(
        mode=RUN_MODE_PAPER_AND_LIVE,
        snapshot_path="market_snapshots.jsonl",
        shadow_events_path="shadow_events.jsonl",
        execution_events_path="execution_events.jsonl",
        snapshot_runner=snapshot_runner,
        shadow_runner=shadow_runner,
        live_runner=live_runner,
    )

    assert result["success"] is True
    assert calls == [
        ("snapshot", "market_snapshots.jsonl"),
        ("paper", "shadow_events.jsonl"),
        ("live", "execution_events.jsonl"),
    ]


def test_run_dashboard_mode_stops_when_automatic_data_fetch_fails():
    calls = []

    def snapshot_runner(args):
        calls.append(("snapshot", args.snapshots))
        return 1

    def shadow_runner(args):
        calls.append(("paper", args.events))
        return 0

    def live_runner(args):
        calls.append(("live", args.events))
        return 0

    result = run_dashboard_mode(
        mode=RUN_MODE_PAPER_AND_LIVE,
        snapshot_path="market_snapshots.jsonl",
        shadow_events_path="shadow_events.jsonl",
        execution_events_path="execution_events.jsonl",
        snapshot_runner=snapshot_runner,
        shadow_runner=shadow_runner,
        live_runner=live_runner,
    )

    assert result["success"] is False
    assert calls == [("snapshot", "market_snapshots.jsonl")]
    assert result["snapshot_exit_code"] == 1
    assert result["paper_exit_code"] is None
    assert result["live_exit_code"] is None
