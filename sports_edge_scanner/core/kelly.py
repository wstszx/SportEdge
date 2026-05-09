from sports_edge_scanner.core.pricing import validate_price, validate_probability


def kelly_fraction(fair_probability: float, price: float) -> float:
    fair = validate_probability(fair_probability, "fair_probability")
    cost = validate_price(price)
    net_profit = 1.0 - cost
    loss = cost
    edge = fair * net_profit - (1.0 - fair) * loss
    if edge <= 0.0:
        return 0.0
    return edge / net_profit


def fractional_kelly(
    fair_probability: float,
    price: float,
    fraction: float = 0.25,
    cap: float = 0.05,
) -> float:
    if fraction < 0.0 or fraction > 1.0:
        raise ValueError("fraction must be between 0 and 1")
    if cap < 0.0 or cap > 1.0:
        raise ValueError("cap must be between 0 and 1")
    sized = kelly_fraction(fair_probability, price) * fraction
    return min(sized, cap)
