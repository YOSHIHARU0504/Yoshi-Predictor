import pytest

from football_predictor.models.counts import count_market


def test_count_market_probabilities_sum_to_one():
    result = count_market(5.2, 4.1, 8.5, "corners")
    assert result["over"] + result["under"] + result["push"] == pytest.approx(1.0)


def test_integer_line_reports_push_probability():
    result = count_market(5.0, 4.0, 9, "yellow_cards")
    assert result["push"] > 0
    assert result["over"] + result["under"] + result["push"] == pytest.approx(1.0)


def test_rejects_unknown_market():
    with pytest.raises(ValueError):
        count_market(5, 4, 8.5, "offsides")
