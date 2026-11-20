"""Chronological Elo model with an explicit draw component."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def elo_probabilities(home_rating: float, away_rating: float, home_advantage: float = 60.0,
                      draw_parameter: float = 1.25) -> dict[str, float]:
    if draw_parameter <= 0:
        raise ValueError("draw_parameter must be positive")
    import math

    q = 10 ** ((home_rating + home_advantage - away_rating) / 400.0)
    draw_weight = draw_parameter * math.sqrt(q)
    denominator = q + 1.0 + draw_weight
    return {
        "home": q / denominator,
        "draw": draw_weight / denominator,
        "away": 1.0 / denominator,
    }


def run_elo_backtest(fixtures: list[dict[str, Any]], initial_rating: float = 1500.0,
                     k_factor: float = 20.0, home_advantage: float = 60.0) -> dict[str, Any]:
    """Replay finished matches in kickoff order; each prediction precedes its rating update."""
    ratings: defaultdict[int, float] = defaultdict(lambda: initial_rating)
    ordered = sorted(fixtures, key=lambda f: (f.get("kickoff_utc") or "", f.get("fixture_id") or 0))
    evaluated = 0
    correct = 0
    brier_sum = 0.0
    rows = []

    for match in ordered:
        if match.get("home_goals") is None or match.get("away_goals") is None:
            continue
        home_id, away_id = match.get("home_team_id"), match.get("away_team_id")
        if home_id is None or away_id is None:
            continue

        probabilities = elo_probabilities(
            ratings[home_id], ratings[away_id], home_advantage=home_advantage
        )
        hg, ag = int(match["home_goals"]), int(match["away_goals"])
        actual = "home" if hg > ag else "away" if hg < ag else "draw"
        predicted = max(probabilities, key=probabilities.get)
        correct += int(predicted == actual)
        brier_sum += sum(
            (probabilities[outcome] - float(outcome == actual)) ** 2
            for outcome in ("home", "draw", "away")
        )
        evaluated += 1
        rows.append({
            "fixture_id": match.get("fixture_id"),
            "actual": actual,
            "predicted": predicted,
            "probabilities": probabilities,
        })

        actual_score = 1.0 if hg > ag else 0.0 if hg < ag else 0.5
        expected_score = probabilities["home"] + 0.5 * probabilities["draw"]
        margin_multiplier = min(2.0, max(1.0, abs(hg - ag) ** 0.5))
        change = k_factor * margin_multiplier * (actual_score - expected_score)
        ratings[home_id] += change
        ratings[away_id] -= change

    return {
        "model": "elo_davidson_chronological",
        "evaluated_matches": evaluated,
        "accuracy": correct / evaluated if evaluated else None,
        "brier_score": brier_sum / evaluated if evaluated else None,
        "ratings": {str(team_id): round(rating, 2) for team_id, rating in ratings.items()},
        "predictions": rows,
        "warning": "Backtest exploratorio. Requiere volumen suficiente y evaluación walk-forward por competición.",
    }
