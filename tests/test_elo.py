import pytest

from football_predictor.models.elo import elo_probabilities, run_elo_backtest


def test_elo_probabilities_sum_to_one():
    probs = elo_probabilities(1500, 1500)
    assert sum(probs.values()) == pytest.approx(1.0)


def test_stronger_home_team_has_higher_home_probability():
    weak = elo_probabilities(1500, 1500)
    strong = elo_probabilities(1750, 1500)
    assert strong["home"] > weak["home"]


def test_backtest_predicts_before_updating_ratings():
    fixtures = [
        {"fixture_id": 1, "kickoff_utc": "2026-01-01", "home_team_id": 1,
         "away_team_id": 2, "home_goals": 2, "away_goals": 0},
        {"fixture_id": 2, "kickoff_utc": "2026-01-08", "home_team_id": 2,
         "away_team_id": 1, "home_goals": 0, "away_goals": 1},
    ]
    result = run_elo_backtest(fixtures)
    assert result["evaluated_matches"] == 2
    assert result["brier_score"] is not None
    assert result["predictions"][0]["fixture_id"] == 1
