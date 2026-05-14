import argparse
from pathlib import Path

from sports_edge_scanner.cli import _live_run, _shadow_watch, _snapshot_collect
from sports_edge_scanner.core.ledger import (
    append_record,
    paper_settlement_record,
    paper_trade_record,
    read_records,
)
from sports_edge_scanner.core.events import read_events
from sports_edge_scanner.core.execution_reports import build_execution_report
from sports_edge_scanner.core.live_status import build_live_status
from sports_edge_scanner.core.snapshots import read_snapshots
from sports_edge_scanner.dashboard_data import build_dashboard_state, price_history_for_market

try:
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by manual launch
    raise SystemExit(
        "Streamlit is not installed. Run: python -m pip install -e .[dashboard]"
    ) from exc


UI_TEXT = {
    "app_title": "体育下注研究仪表盘",
    "app_caption": "本地研究与执行工具。只有显式启用实盘配置后才会提交真实订单。",
    "data": "数据",
    "ledger_path": "交易记录文件",
    "snapshot_path": "市场快照文件",
    "shadow_events_path": "影子事件文件",
    "execution_events_path": "实盘审计事件文件",
    "live_config_path": "实盘安全配置文件",
    "polymarket_auth_config_path": "Polymarket 实盘配置文件",
    "sidebar_help": "数据会在启动所选运行模式时自动采集；这些路径通常保持默认即可。",
    "realized_pnl": "已结算盈亏",
    "realized_roi": "已结算收益率",
    "win_rate": "胜率",
    "average_clv": "平均收盘价优势",
    "max_drawdown": "最大回撤",
    "snapshots": "快照数",
    "markets_tab": "市场",
    "paper_trades_tab": "模拟交易",
    "settlements_tab": "结算",
    "quality_tab": "数据质量",
    "shadow_tab": "影子交易",
    "live_execution_tab": "实盘执行",
    "control_tab": "控制台",
    "raw_report_tab": "原始报告",
    "latest_markets": "最新市场",
    "price_history": "价格历史",
    "no_markets": "先采集快照，市场历史会显示在这里。",
    "paper_trades": "模拟交易",
    "add_trade_caption": "记录一笔仅用于研究的模拟交易。",
    "market_title_or_id": "市场标题或 ID",
    "market_id": "市场 ID",
    "side": "方向",
    "entry_price": "入场价格",
    "stake_size": "投入金额",
    "note": "备注",
    "add_trade": "新增模拟交易",
    "trade_recorded": "模拟交易已记录。",
    "settlements": "结算记录",
    "add_settlement_caption": "记录某个市场最终胜出的方向。",
    "winning_side": "胜出方向",
    "add_settlement": "新增结算",
    "settlement_recorded": "结算已记录。",
    "data_quality": "数据质量",
    "markets": "市场数",
    "time_span": "覆盖时长",
    "candidates": "候选快照",
    "missing_prices": "缺失价格",
    "recent_missing_prices": "最近缺价",
    "unmatched_trades": "未匹配交易",
    "report": "报告",
    "quality": "质量",
    "quality_ok": "当前文件没有数据质量告警。",
    "shadow_overview": "影子交易概览",
    "shadow_quality_clean": "影子交易数据质量当前无警告。",
    "shadow_exposure_market": "按市场暴露",
    "shadow_exposure_outcome": "按结果暴露",
    "shadow_risk_decisions": "风控决策",
    "shadow_fills": "影子成交",
    "shadow_raw_report": "影子原始报告",
    "strategy_diagnostics": "策略诊断",
    "diagnostic_status": "诊断状态",
    "diagnostic_issues": "诊断问题",
    "diagnostic_next_actions": "下一步建议",
    "shadow_controls": "运行模式控制",
    "run_mode": "运行模式",
    "run_mode_paper": "仅纸面",
    "run_mode_live": "仅实盘",
    "run_mode_paper_and_live": "纸面+实盘",
    "start_selected_run_mode": "启动所选模式",
    "automatic_data_fetch": "自动采集数据",
    "automatic_data_fetch_help": "启动任一模式时，系统会先自动采集市场数据，再执行所选运行流程。",
    "advanced_settings": "高级设置",
    "shadow_limit": "市场数量",
    "shadow_iterations": "采集次数",
    "shadow_interval_seconds": "间隔秒数",
    "auto_fair_min_confidence": "自动概率最低置信度",
    "shadow_config_path": "影子配置文件（可选）",
    "mode_run_succeeded": "所选运行模式已完成，请查看状态和报告。",
    "mode_run_failed": "所选运行模式未完成，请查看事件日志和安全状态。",
    "snapshot_collection_failed": "自动数据采集失败，后续运行已停止。",
    "readiness": "准入状态",
    "readiness_blockers": "准入阻断原因",
    "live_safety_status": "实盘安全状态",
    "live_safety_message": "实盘模式会复用纸面交易的信号、风控和订单生成流程；只有执行端会在配置启用后提交真实订单。",
    "live_execution_overview": "实盘执行概览",
    "submitted_live_orders": "已提交实盘订单",
    "rejected_live_orders": "已拒绝实盘订单",
    "latest_execution_status": "最近执行状态",
    "live_ready": "实盘就绪",
    "live_blockers": "实盘阻断原因",
    "live_execution_orders": "实盘订单明细",
    "live_execution_raw_report": "实盘原始报告",
    "run_count": "运行次数",
    "accepted_orders": "通过订单",
    "rejected_orders": "拒绝订单",
    "filled_notional": "已成交名义金额",
    "unfilled_notional": "未成交名义金额",
    "average_slippage": "平均滑点",
    "lack_snapshots": "笔模拟交易缺少快照",
    "missing_yes_no": "条历史快照缺少市场价格",
    "latest_missing_prices": "个市场当前缺少价格",
    "recent_missing_snapshot_prices": "条最近快照缺少市场价格",
    "short_history": "快照历史少于 24 小时",
}


RUN_MODE_PAPER = "paper"
RUN_MODE_LIVE = "live"
RUN_MODE_PAPER_AND_LIVE = "paper_and_live"

RUN_MODE_LABEL_KEYS = {
    RUN_MODE_PAPER: "run_mode_paper",
    RUN_MODE_LIVE: "run_mode_live",
    RUN_MODE_PAPER_AND_LIVE: "run_mode_paper_and_live",
}


TABLE_LABELS = {
    "market_id": "市场 ID",
    "title": "标题",
    "slug": "市场短标识",
    "timestamp": "时间",
    "yes_outcome_name": "主结果",
    "no_outcome_name": "对手结果",
    "yes_price": "主结果价格",
    "no_price": "对手结果价格",
    "liquidity": "流动性",
    "volume": "成交量",
    "signal_status": "信号状态",
    "signal_reasons": "信号原因",
    "side": "方向",
    "price": "价格",
    "size": "投入金额",
    "note": "备注",
    "market": "市场",
    "winning_side": "胜出方向",
    "snapshot_count": "快照数",
    "time_span_hours": "覆盖小时",
    "candidate_snapshot_count": "候选快照",
    "missing_price_snapshot_count": "缺失价格快照",
    "recent_snapshot_count": "最近快照",
    "recent_missing_price_snapshot_count": "最近缺价快照",
    "recent_missing_price_market_count": "最近缺价市场",
    "latest_missing_price_market_count": "当前缺价市场",
    "latest_missing_price": "当前是否缺价",
    "paper_trades": "模拟交易数",
    "settlements": "结算记录数",
    "settled_trades": "已结算交易数",
    "open_trades_with_marks": "有市值标记的未结算交易",
    "snapshots": "快照数",
    "total_staked": "总投入",
    "mark_to_market_pnl": "按市值盈亏",
    "mark_to_market_roi": "按市值收益率",
    "average_clv": "平均收盘价优势",
    "realized_pnl": "已结算盈亏",
    "realized_roi": "已结算收益率",
    "realized_wins": "已结算盈利笔数",
    "realized_losses": "已结算亏损笔数",
    "win_rate": "胜率",
    "max_drawdown": "最大回撤",
    "trades": "交易",
    "entry_price": "入场价格",
    "mark_price": "当前标记价格",
    "pnl": "浮动盈亏",
    "clv": "收盘价优势",
    "settled": "是否结算",
    "snapshot_count": "快照总数",
    "market_count": "市场数",
    "snapshot_time_span_hours": "快照覆盖小时",
    "paper_trade_count": "模拟交易数",
    "paper_trades_missing_snapshots": "缺少快照的模拟交易",
    "markets": "市场列表",
    "market_outcome": "市场/结果",
    "exposure": "暴露",
    "event_type": "事件类型",
    "run_id": "运行 ID",
    "schema_version": "结构版本",
    "allowed": "是否允许",
    "reasons": "原因",
    "requested_notional": "请求名义金额",
    "approved_notional": "批准名义金额",
    "outcome_name": "结果",
    "token_id": "Token ID",
    "status": "状态",
    "latest_status": "最近状态",
    "venue_order_id": "交易所订单 ID",
    "client_order_id": "客户端订单 ID",
    "guard_allowed": "安全检查允许",
    "guard_reasons": "安全检查原因",
    "remaining_notional": "剩余名义金额",
    "message": "消息",
    "live_config_loaded": "实盘配置已加载",
    "auth_config_loaded": "认证配置已加载",
    "mode": "模式",
    "live_enabled": "实盘已启用",
    "kill_switch_enabled": "熔断开关启用",
    "require_confirmation_token": "需要确认令牌",
    "auth_enabled": "认证已启用",
    "allow_live_writes": "允许实盘写入",
    "require_geoblock_check": "需要地区限制检查",
    "credential_status": "凭证状态",
    "missing_credential_envs": "缺失凭证环境变量",
    "filled_notional": "已成交名义金额",
    "unfilled_notional": "未成交名义金额",
    "average_price": "平均价格",
    "slippage": "滑点",
    "order_id": "订单 ID",
    "candidate_count": "候选数",
    "accepted_order_count": "通过订单数",
    "rejected_order_count": "拒绝订单数",
    "orderbook_error_count": "订单簿错误数",
    "simulated_notional_filled": "模拟已成交名义金额",
    "simulated_unfilled_notional": "模拟未成交名义金额",
    "fill_status_counts": "成交状态统计",
    "rejections_by_reason": "拒绝原因统计",
    "exposure_by_market": "按市场暴露",
    "exposure_by_outcome": "按结果暴露",
    "risk_decisions": "风控决策",
    "fills": "成交",
    "data_quality_warnings": "数据质量警告",
}

VALUE_LABELS = {
    "candidate": "候选",
    "watch": "观察",
    "skip": "跳过",
    "trade": "交易",
    "settlement": "结算",
    "YES": "是",
    "NO": "否",
    "yes": "是",
    "no": "否",
    "fair probability clears edge threshold": "公平概率超过优势阈值",
    "no fair probability supplied": "未提供公平概率",
    "missing YES or NO price": "缺少市场价格",
    "missing market prices": "缺少市场价格",
    "low liquidity": "流动性不足",
    "wide spread": "买卖价差过大",
    "market is closed": "市场已关闭",
    "no supplied fair probability clears edge threshold": "已提供的公平概率未超过优势阈值",
    "partial": "部分成交",
    "filled": "已成交",
    "unfilled": "未成交",
    "orderbook errors present": "存在订单簿错误",
    "rejected orders present": "存在被拒绝订单",
    "unfilled shadow orders present": "存在未完全成交的影子订单",
    "candidates present but no fills": "存在候选信号但没有成交",
    "slippage above maximum": "滑点超过上限",
    "stale orderbook": "订单簿过期",
    "shadow scan errors present": "存在影子扫描错误",
    "insufficient shadow runs": "影子运行次数不足",
    "insufficient model estimates": "模型估算数量不足",
    "usable model estimate rate below minimum": "可用模型估算比例低于最低要求",
    "insufficient fills": "模拟成交数量不足",
    "collecting_data": "正在积累数据",
    "needs_independent_signal": "需要独立信号",
    "needs_execution_samples": "需要执行样本",
    "execution_quality_issue": "执行数据质量问题",
    "healthy": "健康",
    "submitted": "已提交",
    "rejected": "已拒绝",
    "dry_run_accepted": "模拟执行已接受",
    "present": "已提供",
    "missing": "缺失",
    "live": "实盘",
    "dry_run": "模拟执行",
    "live config missing": "缺少实盘安全配置",
    "auth config missing": "缺少 Polymarket 实盘配置",
    "live mode is not live": "实盘安全配置未设为 live",
    "live mode disabled": "实盘开关未启用",
    "kill switch enabled": "熔断开关已启用",
    "confirmation token required": "仍要求确认令牌",
    "auth config disabled": "Polymarket 实盘配置未启用",
    "live writes disabled": "实盘写入未启用",
    "credential environment missing": "凭证环境变量缺失",
    "allowed live execution": "允许实盘执行",
    "allowed dry-run execution": "允许模拟执行",
    "insufficient sample size": "样本数量不足",
    "execution data quality issue": "执行数据质量问题",
    "conservative auto fair is not producing edge": "保守自动概率未产生优势",
    "candidate signals have not produced simulated fills": "候选信号尚未产生模拟成交",
    "readiness blockers remain": "仍存在准入阻断",
    "collect more shadow runs": "继续积累影子运行样本",
    "add independent signal source": "接入独立信号来源",
    "continue shadow collection for execution samples": "继续采集执行样本",
    "fix execution data quality before collecting more samples": "先修复执行数据质量再继续采样",
    "improve market filters or model confidence": "改进市场过滤或模型置信度",
    "review readiness blockers": "查看准入阻断原因",
}


def _label(key: str) -> str:
    return UI_TEXT[key]


def _translate_value(value):
    if value is None:
        return "无数据"
    if isinstance(value, str):
        return VALUE_LABELS.get(value, value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return [_translate_value(item) for item in value]
    return value


def _translate_table_value(value):
    if isinstance(value, list):
        return ", ".join(str(_translate_table_value(item)) for item in value)
    if value is None:
        return None
    return _translate_value(value)


def _localize_json(value):
    if isinstance(value, dict):
        return {
            TABLE_LABELS.get(key, key): _localize_json(_translate_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_localize_json(item) for item in value]
    return _translate_value(value)


def _display_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            TABLE_LABELS.get(key, key): _translate_table_value(value)
            for key, value in row.items()
        }
        for row in rows
    ]


def _money(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"${float(value):,.2f}"


def _percent(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


def build_shadow_watch_args(
    *,
    limit: int,
    iterations: int,
    interval_seconds: float,
    config_path: str,
    events_path: str,
    auto_fair_min_confidence: float,
) -> argparse.Namespace:
    return argparse.Namespace(
        limit=limit,
        iterations=iterations,
        interval_seconds=interval_seconds,
        fair="",
        config=config_path,
        events=events_path,
        auto_fair_min_confidence=auto_fair_min_confidence,
        json=True,
        shadow_command="watch",
    )


def build_snapshot_collect_args(
    *,
    limit: int,
    snapshot_path: str,
) -> argparse.Namespace:
    return argparse.Namespace(
        limit=limit,
        snapshots=snapshot_path,
        fair=[],
        snapshot_command="collect",
    )


def build_live_run_args(
    *,
    live_config_path: str,
    auth_config_path: str,
    events_path: str,
    limit: int,
    auto_fair_min_confidence: float,
    confirm_token: str = "",
) -> argparse.Namespace:
    return argparse.Namespace(
        limit=limit,
        fair="",
        auto_fair_min_confidence=auto_fair_min_confidence,
        config="",
        live_config=live_config_path,
        auth_config=auth_config_path,
        events=events_path,
        confirm_token=confirm_token,
        json=True,
        live_command="run",
    )


def build_control_default_paths(
    *,
    snapshot_path: Path,
    shadow_events_path: Path,
    execution_events_path: Path,
    live_config_path: Path,
    auth_config_path: Path,
) -> dict[str, str]:
    def display_path(path: Path) -> str:
        return path.as_posix()

    return {
        "snapshot_path": display_path(snapshot_path),
        "shadow_events_path": display_path(shadow_events_path),
        "execution_events_path": display_path(execution_events_path),
        "live_config_path": display_path(live_config_path),
        "auth_config_path": display_path(auth_config_path),
    }


def run_dashboard_shadow_watch(
    *,
    limit: int,
    iterations: int,
    interval_seconds: float,
    config_path: str,
    events_path: str,
    auto_fair_min_confidence: float,
    runner=_shadow_watch,
) -> int:
    return runner(
        build_shadow_watch_args(
            limit=limit,
            iterations=iterations,
            interval_seconds=interval_seconds,
            config_path=config_path,
            events_path=events_path,
            auto_fair_min_confidence=auto_fair_min_confidence,
        )
    )


def run_dashboard_mode(
    *,
    mode: str,
    snapshot_path: str,
    shadow_events_path: str,
    execution_events_path: str,
    shadow_config_path: str = "shadow_config.json",
    live_config_path: str = "",
    limit: int = 20,
    iterations: int = 3,
    interval_seconds: float = 0.0,
    auto_fair_min_confidence: float = 0.75,
    snapshot_runner=_snapshot_collect,
    shadow_runner=_shadow_watch,
    live_runner=_live_run,
    auth_config_path: str = "polymarket_auth_config.json",
) -> dict[str, int | bool | str | None]:
    if mode not in RUN_MODE_LABEL_KEYS:
        raise ValueError(f"unknown run mode: {mode}")

    snapshot_exit_code = snapshot_runner(
        build_snapshot_collect_args(
            limit=limit,
            snapshot_path=snapshot_path,
        )
    )
    result: dict[str, int | bool | str | None] = {
        "mode": mode,
        "success": snapshot_exit_code == 0,
        "snapshot_exit_code": snapshot_exit_code,
        "paper_exit_code": None,
        "live_exit_code": None,
    }
    if snapshot_exit_code != 0:
        return result

    if mode in {RUN_MODE_PAPER, RUN_MODE_PAPER_AND_LIVE}:
        paper_exit_code = shadow_runner(
            build_shadow_watch_args(
                limit=limit,
                iterations=iterations,
                interval_seconds=interval_seconds,
                config_path=shadow_config_path,
                events_path=shadow_events_path,
                auto_fair_min_confidence=auto_fair_min_confidence,
            )
        )
        result["paper_exit_code"] = paper_exit_code
        result["success"] = result["success"] and paper_exit_code == 0

    if mode in {RUN_MODE_LIVE, RUN_MODE_PAPER_AND_LIVE}:
        live_exit_code = live_runner(
            build_live_run_args(
                live_config_path=live_config_path,
                auth_config_path=auth_config_path,
                events_path=execution_events_path,
                limit=limit,
                auto_fair_min_confidence=auto_fair_min_confidence,
            )
        )
        result["live_exit_code"] = live_exit_code
        result["success"] = result["success"] and live_exit_code == 0

    return result


def _load_state(
    ledger_path: Path,
    snapshot_path: Path,
    shadow_events_path: Path,
) -> tuple[list[dict], list[dict], list[dict], dict]:
    records = read_records(ledger_path)
    snapshots = read_snapshots(snapshot_path)
    shadow_events = read_events(shadow_events_path)
    return records, snapshots, shadow_events, build_dashboard_state(
        records,
        snapshots,
        shadow_events,
    )


def build_dashboard_live_state(
    *,
    execution_events_path: str | Path,
    live_config_path: str | Path,
    auth_config_path: str | Path,
    environ=None,
) -> dict[str, object]:
    execution_events = read_events(Path(execution_events_path))
    return {
        "live_status": build_live_status(
            live_config_path=live_config_path,
            auth_config_path=auth_config_path,
            environ=environ,
        ),
        "execution_report": build_execution_report(execution_events),
        "execution_events": execution_events,
    }


def _render_overview(state: dict) -> None:
    report = state["report"]
    quality = state["quality"]
    metric_columns = st.columns(6)
    metric_columns[0].metric(_label("realized_pnl"), _money(report["realized_pnl"]))
    metric_columns[1].metric(_label("realized_roi"), _percent(report["realized_roi"]))
    metric_columns[2].metric(_label("win_rate"), _percent(report["win_rate"]))
    metric_columns[3].metric(_label("average_clv"), _percent(report["average_clv"]))
    metric_columns[4].metric(_label("max_drawdown"), _money(report["max_drawdown"]))
    metric_columns[5].metric(_label("snapshots"), f"{quality['snapshot_count']:,}")

    warning_parts = []
    if quality["paper_trades_missing_snapshots"]:
        warning_parts.append(
            f"{quality['paper_trades_missing_snapshots']} {_label('lack_snapshots')}"
        )
    if quality.get("recent_missing_price_snapshot_count"):
        warning_parts.append(
            f"{quality['recent_missing_price_snapshot_count']} "
            f"{_label('recent_missing_snapshot_prices')}"
        )
    elif quality["missing_price_snapshot_count"]:
        warning_parts.append(
            f"{quality['missing_price_snapshot_count']} {_label('missing_yes_no')}"
        )
    if quality["snapshot_time_span_hours"] < 24 and quality["snapshot_count"]:
        warning_parts.append(_label("short_history"))

    if warning_parts:
        st.warning(" | ".join(warning_parts))
    else:
        st.success(_label("quality_ok"))


def _render_markets(state: dict, snapshots: list[dict]) -> None:
    st.subheader(_label("latest_markets"))
    latest_markets = state["latest_markets"]
    st.dataframe(_display_rows(latest_markets), width="stretch", hide_index=True)

    if not latest_markets:
        st.info(_label("no_markets"))
        return

    options = {
        f"{row['title']} ({row['market_id']})": row["market_id"]
        for row in latest_markets
    }
    selected_label = st.selectbox(_label("price_history"), list(options))
    history = price_history_for_market(snapshots, options[selected_label])
    chart_history = [
        {
            "时间": row["timestamp"],
            "主结果价格": row["yes_price"] if row["yes_price"] is not None else 0.0,
            "对手结果价格": row["no_price"] if row["no_price"] is not None else 0.0,
        }
        for row in history
    ]
    st.line_chart(
        chart_history,
        x="时间",
        y=["主结果价格", "对手结果价格"],
        width="stretch",
    )
    st.dataframe(_display_rows(history), width="stretch", hide_index=True)


def _render_paper_trades(state: dict, ledger_path: Path) -> None:
    st.subheader(_label("paper_trades"))
    st.dataframe(_display_rows(state["paper_trades"]), width="stretch", hide_index=True)

    with st.form("add-paper-trade", clear_on_submit=True):
        st.caption(_label("add_trade_caption"))
        market = st.text_input(_label("market_title_or_id"))
        market_id = st.text_input(_label("market_id"))
        side_label = st.selectbox(_label("side"), ["是", "否"])
        price = st.number_input(_label("entry_price"), min_value=0.01, max_value=0.99, value=0.50)
        size = st.number_input(_label("stake_size"), min_value=0.01, value=10.0)
        note = st.text_input(_label("note"))
        submitted = st.form_submit_button(_label("add_trade"))
        if submitted:
            record = paper_trade_record(
                market=market or market_id,
                side="YES" if side_label == "是" else "NO",
                price=price,
                size=size,
                note=note,
                metadata={"market_id": market_id} if market_id else {},
            )
            append_record(ledger_path, record)
            st.success(_label("trade_recorded"))
            st.rerun()


def _render_settlements(state: dict, ledger_path: Path) -> None:
    st.subheader(_label("settlements"))
    st.dataframe(_display_rows(state["settlements"]), width="stretch", hide_index=True)

    with st.form("add-settlement", clear_on_submit=True):
        st.caption(_label("add_settlement_caption"))
        market = st.text_input(_label("market_title_or_id"), key="settlement-market")
        market_id = st.text_input(_label("market_id"), key="settlement-market-id")
        winning_side_label = st.selectbox(_label("winning_side"), ["是", "否"])
        note = st.text_input(_label("note"), key="settlement-note")
        submitted = st.form_submit_button(_label("add_settlement"))
        if submitted:
            record = paper_settlement_record(
                market=market or market_id,
                market_id=market_id,
                winning_side="YES" if winning_side_label == "是" else "NO",
                note=note,
            )
            append_record(ledger_path, record)
            st.success(_label("settlement_recorded"))
            st.rerun()


def _render_quality(state: dict) -> None:
    quality = state["quality"]
    st.subheader(_label("data_quality"))
    columns = st.columns(6)
    columns[0].metric(_label("markets"), f"{quality['market_count']:,}")
    columns[1].metric(_label("time_span"), f"{quality['snapshot_time_span_hours']:.2f}h")
    columns[2].metric(_label("candidates"), f"{quality['candidate_snapshot_count']:,}")
    columns[3].metric(
        _label("recent_missing_prices"),
        f"{quality.get('recent_missing_price_snapshot_count', 0):,}",
    )
    columns[4].metric(
        _label("latest_missing_prices"),
        f"{quality.get('recent_missing_price_market_count', 0):,}",
    )
    columns[5].metric(_label("unmatched_trades"), f"{quality['paper_trades_missing_snapshots']:,}")
    st.dataframe(_display_rows(quality["markets"]), width="stretch", hide_index=True)


def _render_readiness(readiness: dict) -> None:
    status = "READY" if readiness.get("ready") else "NOT READY"
    st.metric(_label("readiness"), status)
    blockers = readiness.get("blockers") or []
    if blockers:
        st.warning(
            f"{_label('readiness_blockers')}: "
            + " | ".join(_translate_value(item) for item in blockers)
        )


def _render_live_status(status: dict) -> None:
    st.metric(_label("live_ready"), "READY" if status.get("ready") else "NOT READY")
    blockers = status.get("blockers") or []
    if blockers:
        st.warning(
            f"{_label('live_blockers')}: "
            + " | ".join(_translate_value(item) for item in blockers)
        )
    rows = [
        {
            "live_config_loaded": status.get("live_config_loaded"),
            "auth_config_loaded": status.get("auth_config_loaded"),
            "mode": status.get("mode"),
            "live_enabled": status.get("live_enabled"),
            "kill_switch_enabled": status.get("kill_switch_enabled"),
            "auth_enabled": status.get("auth_enabled"),
            "allow_live_writes": status.get("allow_live_writes"),
            "credential_status": status.get("credential_status"),
            "missing_credential_envs": ", ".join(
                status.get("missing_credential_envs") or []
            ),
        }
    ]
    st.dataframe(_display_rows(rows), width="stretch", hide_index=True)


def _render_strategy_diagnostics(report: dict) -> None:
    diagnostics = report.get("strategy_diagnostics") or {}
    st.subheader(_label("strategy_diagnostics"))
    st.metric(_label("diagnostic_status"), _translate_value(diagnostics.get("status")))

    issues = diagnostics.get("issues") or []
    if issues:
        st.warning(
            f"{_label('diagnostic_issues')}: "
            + " | ".join(_translate_value(item) for item in issues)
        )

    next_actions = diagnostics.get("next_actions") or []
    if next_actions:
        st.info(
            f"{_label('diagnostic_next_actions')}: "
            + " | ".join(_translate_value(item) for item in next_actions)
        )


def _render_controls(
    state: dict,
    snapshot_path: Path,
    shadow_events_path: Path,
    execution_events_path: Path,
    live_config_path: Path,
    auth_config_path: Path,
) -> None:
    default_paths = build_control_default_paths(
        snapshot_path=snapshot_path,
        shadow_events_path=shadow_events_path,
        execution_events_path=execution_events_path,
        live_config_path=live_config_path,
        auth_config_path=auth_config_path,
    )
    st.subheader(_label("shadow_controls"))
    st.info(_label("automatic_data_fetch_help"))
    with st.form("run-mode-controls"):
        mode_options = list(RUN_MODE_LABEL_KEYS)
        mode_labels = [_label(RUN_MODE_LABEL_KEYS[mode]) for mode in mode_options]
        selected_mode_label = st.radio(
            _label("run_mode"),
            mode_labels,
            horizontal=True,
        )
        selected_mode = mode_options[mode_labels.index(selected_mode_label)]

        with st.expander(_label("advanced_settings"), expanded=False):
            snapshot_path_value = st.text_input(
                _label("snapshot_path"),
                default_paths["snapshot_path"],
                key="control-snapshot-path",
            )
            events_path = st.text_input(
                _label("shadow_events_path"),
                default_paths["shadow_events_path"],
                key="control-shadow-events",
            )
            execution_events_path_value = st.text_input(
                _label("execution_events_path"),
                default_paths["execution_events_path"],
                key="control-execution-events",
            )
            config_path = st.text_input(
                _label("shadow_config_path"),
                value="",
                key="control-shadow-config",
            )
            live_config_path = st.text_input(
                _label("live_config_path"),
                default_paths["live_config_path"],
                key="control-live-config",
            )
            auth_config_path = st.text_input(
                _label("polymarket_auth_config_path"),
                default_paths["auth_config_path"],
                key="control-auth-config",
            )
            columns = st.columns(4)
            limit = columns[0].number_input(
                _label("shadow_limit"),
                min_value=1,
                max_value=100,
                value=20,
                step=1,
            )
            iterations = columns[1].number_input(
                _label("shadow_iterations"),
                min_value=1,
                max_value=20,
                value=3,
                step=1,
            )
            interval_seconds = columns[2].number_input(
                _label("shadow_interval_seconds"),
                min_value=0.0,
                value=0.0,
                step=1.0,
            )
            min_confidence = columns[3].number_input(
                _label("auto_fair_min_confidence"),
                min_value=0.0,
                max_value=1.0,
                value=0.75,
                step=0.05,
            )
        run_mode = st.form_submit_button(_label("start_selected_run_mode"))

    if run_mode:
        result = run_dashboard_mode(
            mode=selected_mode,
            snapshot_path=snapshot_path_value,
            shadow_events_path=events_path,
            execution_events_path=execution_events_path_value,
            shadow_config_path=config_path,
            live_config_path=live_config_path,
            auth_config_path=auth_config_path,
            limit=int(limit),
            iterations=int(iterations),
            interval_seconds=float(interval_seconds),
            auto_fair_min_confidence=float(min_confidence),
        )
        if result["success"]:
            st.success(_label("mode_run_succeeded"))
            st.rerun()
        elif result["snapshot_exit_code"] != 0:
            st.error(_label("snapshot_collection_failed"))
        else:
            st.error(_label("mode_run_failed"))

    _render_readiness(state["shadow_report"].get("readiness", {}))
    _render_strategy_diagnostics(state["shadow_report"])
    st.subheader(_label("live_safety_status"))
    st.info(_label("live_safety_message"))


def _render_live_execution(live_state: dict) -> None:
    report = live_state["execution_report"]
    st.subheader(_label("live_safety_status"))
    _render_live_status(live_state["live_status"])
    st.subheader(_label("live_execution_overview"))
    columns = st.columns(5)
    columns[0].metric(_label("run_count"), f"{report['run_count']:,}")
    columns[1].metric(
        _label("submitted_live_orders"),
        f"{report['submitted_order_count']:,}",
    )
    columns[2].metric(
        _label("rejected_live_orders"),
        f"{report['rejected_order_count']:,}",
    )
    columns[3].metric(_label("filled_notional"), _money(report["filled_notional"]))
    columns[4].metric(
        _label("latest_execution_status"),
        _translate_value(report.get("latest_status")),
    )
    st.subheader(_label("live_execution_orders"))
    st.dataframe(_display_rows(report["orders"]), width="stretch", hide_index=True)
    st.subheader(_label("live_execution_raw_report"))
    st.json(_localize_json(report))


def _render_shadow(state: dict) -> None:
    report = state["shadow_report"]
    st.subheader(_label("shadow_overview"))
    columns = st.columns(6)
    columns[0].metric(_label("candidates"), f"{report['candidate_count']:,}")
    columns[1].metric(_label("accepted_orders"), f"{report['accepted_order_count']:,}")
    columns[2].metric(_label("rejected_orders"), f"{report['rejected_order_count']:,}")
    columns[3].metric(_label("filled_notional"), _money(report["simulated_notional_filled"]))
    columns[4].metric(_label("unfilled_notional"), _money(report["simulated_unfilled_notional"]))
    columns[5].metric(_label("average_slippage"), f"{report['average_slippage']:.4f}")

    if report["data_quality_warnings"]:
        st.warning(" | ".join(_translate_value(item) for item in report["data_quality_warnings"]))
    else:
        st.success(_label("shadow_quality_clean"))

    _render_strategy_diagnostics(report)

    st.subheader(_label("shadow_exposure_market"))
    st.dataframe(
        _display_rows(state["shadow_exposure_by_market"]),
        width="stretch",
        hide_index=True,
    )
    st.subheader(_label("shadow_exposure_outcome"))
    st.dataframe(
        _display_rows(state["shadow_exposure_by_outcome"]),
        width="stretch",
        hide_index=True,
    )
    st.subheader(_label("shadow_risk_decisions"))
    st.dataframe(
        _display_rows(state["shadow_risk_decisions"]),
        width="stretch",
        hide_index=True,
    )
    st.subheader(_label("shadow_fills"))
    st.dataframe(
        _display_rows(state["shadow_fills"]),
        width="stretch",
        hide_index=True,
    )
    st.subheader(_label("shadow_raw_report"))
    st.json(_localize_json(report))


def main() -> None:
    st.set_page_config(
        page_title=_label("app_title"),
        page_icon="SES",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        #MainMenu,
        footer {
            visibility: hidden;
            height: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(_label("app_title"))
    st.caption(_label("app_caption"))

    with st.sidebar:
        st.header(_label("data"))
        st.caption(_label("sidebar_help"))
        with st.sidebar.expander(_label("advanced_settings"), expanded=False):
            ledger_path = Path(st.text_input(_label("ledger_path"), "paper_trades.jsonl"))
            snapshot_path = Path(
                st.text_input(_label("snapshot_path"), "market_snapshots.jsonl")
            )
            shadow_events_path = Path(
                st.text_input(_label("shadow_events_path"), "shadow_events.jsonl")
            )
            execution_events_path = Path(
                st.text_input(_label("execution_events_path"), "execution_events.jsonl")
            )
            live_config_path = Path(
                st.text_input(_label("live_config_path"), "live_config.json")
            )
            auth_config_path = Path(
                st.text_input(
                    _label("polymarket_auth_config_path"),
                    "polymarket_auth_config.json",
                )
            )

    records, snapshots, _shadow_events, state = _load_state(
        ledger_path,
        snapshot_path,
        shadow_events_path,
    )
    live_state = build_dashboard_live_state(
        execution_events_path=execution_events_path,
        live_config_path=live_config_path,
        auth_config_path=auth_config_path,
    )
    _render_overview(state)

    (
        markets_tab,
        trades_tab,
        settlements_tab,
        quality_tab,
        shadow_tab,
        live_execution_tab,
        control_tab,
        raw_tab,
    ) = st.tabs(
        [
            _label("markets_tab"),
            _label("paper_trades_tab"),
            _label("settlements_tab"),
            _label("quality_tab"),
            _label("shadow_tab"),
            _label("live_execution_tab"),
            _label("control_tab"),
            _label("raw_report_tab"),
        ]
    )
    with markets_tab:
        _render_markets(state, snapshots)
    with trades_tab:
        _render_paper_trades(state, ledger_path)
    with settlements_tab:
        _render_settlements(state, ledger_path)
    with quality_tab:
        _render_quality(state)
    with shadow_tab:
        _render_shadow(state)
    with live_execution_tab:
        _render_live_execution(live_state)
    with control_tab:
        _render_controls(
            state,
            snapshot_path,
            shadow_events_path,
            execution_events_path,
            live_config_path,
            auth_config_path,
        )
    with raw_tab:
        st.subheader(_label("report"))
        st.json(_localize_json(state["report"]))
        st.subheader(_label("quality"))
        st.json(_localize_json(state["quality"]))


if __name__ == "__main__":
    main()
