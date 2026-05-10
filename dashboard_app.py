from pathlib import Path

from sports_edge_scanner.core.ledger import (
    append_record,
    paper_settlement_record,
    paper_trade_record,
    read_records,
)
from sports_edge_scanner.core.events import read_events
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
    "app_caption": "本地研究工具。不会自动下注，也不会操作钱包。",
    "data": "数据",
    "ledger_path": "交易记录文件",
    "snapshot_path": "市场快照文件",
    "shadow_events_path": "影子事件文件",
    "sidebar_help": "请先在命令行采集快照，然后刷新这个仪表盘。",
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
    "accepted_orders": "通过订单",
    "rejected_orders": "拒绝订单",
    "filled_notional": "已成交名义金额",
    "unfilled_notional": "未成交名义金额",
    "average_slippage": "平均滑点",
    "lack_snapshots": "笔模拟交易缺少快照",
    "missing_yes_no": "条快照缺少是/否价格",
    "short_history": "快照历史少于 24 小时",
}


TABLE_LABELS = {
    "market_id": "市场 ID",
    "title": "标题",
    "slug": "市场短标识",
    "timestamp": "时间",
    "yes_price": "是价格",
    "no_price": "否价格",
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
    "missing YES or NO price": "缺少 YES/NO 价格",
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
        {TABLE_LABELS.get(key, key): _translate_value(value) for key, value in row.items()}
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
    if quality["missing_price_snapshot_count"]:
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
    st.dataframe(_display_rows(latest_markets), use_container_width=True, hide_index=True)

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
            "是价格": row["yes_price"] if row["yes_price"] is not None else 0.0,
            "否价格": row["no_price"] if row["no_price"] is not None else 0.0,
        }
        for row in history
    ]
    st.line_chart(
        chart_history,
        x="时间",
        y=["是价格", "否价格"],
        use_container_width=True,
    )
    st.dataframe(_display_rows(history), use_container_width=True, hide_index=True)


def _render_paper_trades(state: dict, ledger_path: Path) -> None:
    st.subheader(_label("paper_trades"))
    st.dataframe(_display_rows(state["paper_trades"]), use_container_width=True, hide_index=True)

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
    st.dataframe(_display_rows(state["settlements"]), use_container_width=True, hide_index=True)

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
    columns = st.columns(5)
    columns[0].metric(_label("markets"), f"{quality['market_count']:,}")
    columns[1].metric(_label("time_span"), f"{quality['snapshot_time_span_hours']:.2f}h")
    columns[2].metric(_label("candidates"), f"{quality['candidate_snapshot_count']:,}")
    columns[3].metric(_label("missing_prices"), f"{quality['missing_price_snapshot_count']:,}")
    columns[4].metric(_label("unmatched_trades"), f"{quality['paper_trades_missing_snapshots']:,}")
    st.dataframe(_display_rows(quality["markets"]), use_container_width=True, hide_index=True)


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

    st.subheader(_label("shadow_exposure_market"))
    st.dataframe(
        _display_rows(state["shadow_exposure_by_market"]),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader(_label("shadow_exposure_outcome"))
    st.dataframe(
        _display_rows(state["shadow_exposure_by_outcome"]),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader(_label("shadow_risk_decisions"))
    st.dataframe(
        _display_rows(state["shadow_risk_decisions"]),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader(_label("shadow_fills"))
    st.dataframe(
        _display_rows(state["shadow_fills"]),
        use_container_width=True,
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
        ledger_path = Path(st.text_input(_label("ledger_path"), "paper_trades.jsonl"))
        snapshot_path = Path(st.text_input(_label("snapshot_path"), "market_snapshots.jsonl"))
        shadow_events_path = Path(st.text_input(_label("shadow_events_path"), "shadow_events.jsonl"))
        st.caption(_label("sidebar_help"))

    records, snapshots, _shadow_events, state = _load_state(
        ledger_path,
        snapshot_path,
        shadow_events_path,
    )
    _render_overview(state)

    markets_tab, trades_tab, settlements_tab, quality_tab, shadow_tab, raw_tab = st.tabs(
        [
            _label("markets_tab"),
            _label("paper_trades_tab"),
            _label("settlements_tab"),
            _label("quality_tab"),
            _label("shadow_tab"),
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
    with raw_tab:
        st.subheader(_label("report"))
        st.json(_localize_json(state["report"]))
        st.subheader(_label("quality"))
        st.json(_localize_json(state["quality"]))


if __name__ == "__main__":
    main()
