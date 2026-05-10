from sports_edge_scanner.models import OrderBook, ShadowFill, ShadowOrder


def simulate_buy_limit_fill(order: ShadowOrder, orderbook: OrderBook) -> ShadowFill:
    remaining_notional = order.notional
    filled_notional = 0.0
    filled_contracts = 0.0
    consumed: list[dict[str, float]] = []
    best_ask = orderbook.best_ask

    for level in sorted(orderbook.asks, key=lambda item: item.price):
        if level.price > order.limit_price or remaining_notional <= 0.0:
            break
        level_notional = level.price * level.size
        take_notional = min(remaining_notional, level_notional)
        take_contracts = take_notional / level.price
        filled_notional += take_notional
        filled_contracts += take_contracts
        remaining_notional -= take_notional
        consumed.append(
            {
                "price": level.price,
                "notional": take_notional,
                "contracts": take_contracts,
            }
        )

    if filled_notional == 0.0:
        status = "unfilled"
        average_price = None
    elif remaining_notional > 1e-9:
        status = "partial"
        average_price = filled_notional / filled_contracts
    else:
        status = "full"
        average_price = filled_notional / filled_contracts

    slippage = 0.0
    if average_price is not None and best_ask is not None:
        slippage = average_price - best_ask

    return ShadowFill(
        order_id=order.order_id,
        status=status,
        requested_notional=order.notional,
        filled_notional=filled_notional,
        filled_contracts=filled_contracts,
        average_price=average_price,
        unfilled_notional=max(0.0, remaining_notional),
        slippage=slippage,
        consumed_levels=consumed,
    )
