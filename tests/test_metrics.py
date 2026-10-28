import math

import pytest

from metrics import etx, path_etx


def test_etx_uses_forward_and_reverse_delivery_probabilities():
    assert etx(0.5, 0.8) == pytest.approx(2.5)


@pytest.mark.parametrize("probability", [0.0, -0.1, 1.01, math.inf, math.nan])
def test_etx_rejects_invalid_probabilities(probability):
    with pytest.raises(ValueError):
        etx(probability, 1.0)


def test_path_etx_is_sum_of_link_etx_values():
    links = [
        {"u": "A", "v": "B", "forward": 0.5, "reverse": 1.0, "available": True},
        {"u": "B", "v": "C", "forward": 1.0, "reverse": 0.5, "available": True},
    ]
    assert path_etx(["A", "B", "C"], links) == pytest.approx(4.0)


def test_path_etx_returns_infinity_for_unavailable_link():
    links = [{"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": False}]
    assert math.isinf(path_etx(["A", "B"], links))
