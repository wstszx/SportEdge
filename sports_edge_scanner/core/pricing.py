def validate_price(price: float) -> float:
    if price <= 0.0 or price >= 1.0:
        raise ValueError("price must be between 0 and 1, exclusive")
    return float(price)


def validate_probability(probability: float, name: str = "probability") -> float:
    if probability < 0.0 or probability > 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return float(probability)


def implied_probability(price: float) -> float:
    return validate_price(price)


def break_even_probability(price: float, cost_buffer: float = 0.0) -> float:
    validate_probability(cost_buffer, "cost_buffer")
    threshold = validate_price(price) + cost_buffer
    if threshold >= 1.0:
        raise ValueError("price plus cost_buffer must be less than 1")
    return threshold


def expected_value_per_unit(
    fair_probability: float,
    price: float,
    cost_buffer: float = 0.0,
) -> float:
    fair = validate_probability(fair_probability, "fair_probability")
    return fair - break_even_probability(price, cost_buffer)
