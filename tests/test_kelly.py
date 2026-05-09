import pytest

from sports_edge_scanner.core.kelly import fractional_kelly, kelly_fraction


def test_kelly_fraction_is_zero_when_fair_probability_is_not_above_price():
    assert kelly_fraction(0.50, 0.52) == 0.0


def test_kelly_fraction_for_binary_contract_edge():
    assert kelly_fraction(0.55, 0.47) == pytest.approx(0.1509433962)


def test_fractional_kelly_applies_fraction_and_cap():
    assert fractional_kelly(0.55, 0.47, fraction=0.25, cap=0.05) == pytest.approx(
        0.037735849
    )


def test_fractional_kelly_caps_large_edges():
    assert fractional_kelly(0.90, 0.20, fraction=0.25, cap=0.05) == pytest.approx(0.05)


@pytest.mark.parametrize(
    "fair_probability,price",
    [(-0.1, 0.5), (1.1, 0.5), (0.5, 0.0), (0.5, 1.0)],
)
def test_kelly_rejects_invalid_inputs(fair_probability, price):
    with pytest.raises(ValueError):
        kelly_fraction(fair_probability, price)
