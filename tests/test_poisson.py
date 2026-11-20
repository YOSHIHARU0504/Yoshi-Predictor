import pytest

from football_predictor.models.poisson import predict_goal_markets, score_matrix


def test_result_probabilities_sum_to_one():
    result = predict_goal_markets(1.45, 1.10)
    assert sum(result["result_1x2"].values()) == pytest.approx(1.0, abs=1e-10)


def test_btts_complements_sum_to_one():
    result = predict_goal_markets(1.45, 1.10)
    assert result["btts"]["yes"] + result["btts"]["no"] == pytest.approx(1.0)


def test_over_probabilities_are_monotonic():
    totals = predict_goal_markets(1.7, 1.2)["total_goals"]
    values = [totals[str(line)]["over"] for line in (0.5, 1.5, 2.5, 3.5, 4.5)]
    assert values == sorted(values, reverse=True)


def test_score_matrix_has_valid_probabilities():
    matrix = score_matrix(1.3, 0.9)
    assert all(0 <= p <= 1 for row in matrix for p in row)
    assert sum(map(sum, matrix)) <= 1.0


@pytest.mark.parametrize("home,away", [(-1, 1), (1, -1), (11, 1)])
def test_invalid_expected_goals_are_rejected(home, away):
    with pytest.raises(ValueError):
        predict_goal_markets(home, away)
