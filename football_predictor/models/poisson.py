"""Independent Poisson goal model and derived full-time markets."""
from __future__ import annotations

from math import exp, factorial
from typing import Any


def _pmf(rate: float, goals: int) -> float:
    if rate < 0:
        raise ValueError("Poisson rate must be non-negative")
    return exp(-rate) * rate**goals / factorial(goals)


def _validate(lambda_home: float, lambda_away: float) -> None:
    if not (0 <= lambda_home <= 10 and 0 <= lambda_away <= 10):
        raise ValueError("Expected goals must be between 0 and 10")


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> list[list[float]]:
    """Return a truncated independent score probability matrix."""
    _validate(lambda_home, lambda_away)
    if not 1 <= max_goals <= 40:
        raise ValueError("max_goals must be between 1 and 40")
    home = [_pmf(lambda_home, g) for g in range(max_goals + 1)]
    away = [_pmf(lambda_away, g) for g in range(max_goals + 1)]
    return [[ph * pa for pa in away] for ph in home]


def predict_goal_markets(lambda_home: float, lambda_away: float) -> dict[str, Any]:
    """Calculate 1X2, BTTS, totals and scoreline probabilities from expected goals."""
    _validate(lambda_home, lambda_away)
    matrix = score_matrix(lambda_home, lambda_away, max_goals=30)
    mass = sum(sum(row) for row in matrix)
    if mass <= 0:
        raise ValueError("Probability mass is zero")
    grid = [[p / mass for p in row] for row in matrix]

    home_win = sum(grid[h][a] for h in range(31) for a in range(31) if h > a)
    draw = sum(grid[g][g] for g in range(31))
    away_win = sum(grid[h][a] for h in range(31) for a in range(31) if h < a)
    btts = sum(grid[h][a] for h in range(1, 31) for a in range(1, 31))

    totals: dict[str, dict[str, float]] = {}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        over = sum(grid[h][a] for h in range(31) for a in range(31) if h + a > line)
        totals[str(line)] = {"over": over, "under": 1.0 - over}

    top_scores = sorted(
        ({"score": f"{h}-{a}", "probability": grid[h][a]} for h in range(31) for a in range(31)),
        key=lambda item: item["probability"],
        reverse=True,
    )[:5]

    return {
        "expected_goals": {"home": lambda_home, "away": lambda_away},
        "result_1x2": {"home": home_win, "draw": draw, "away": away_win},
        "btts": {"yes": btts, "no": 1.0 - btts},
        "total_goals": totals,
        "most_likely_scores": top_scores,
        "model": "independent_poisson_baseline",
        "warning": "Baseline matemático; no es un pronóstico real sin lambdas entrenadas y validadas.",
    }
