"""Poisson count-market calculator for corners and disciplinary events."""
from __future__ import annotations

from math import exp, factorial


def _distribution(rate: float, cap: int = 40) -> list[float]:
    if not 0 <= rate <= 40:
        raise ValueError("Expected count must be between 0 and 40")
    values = [exp(-rate) * rate**k / factorial(k) for k in range(cap + 1)]
    mass = sum(values)
    return [v / mass for v in values]


def count_market(lambda_home: float, lambda_away: float, line: float,
                 market: str = "corners") -> dict:
    if market not in {"corners", "yellow_cards", "red_cards"}:
        raise ValueError("Unsupported count market")
    if not 0 <= line <= 40:
        raise ValueError("Line must be between 0 and 40")
    home = _distribution(lambda_home)
    away = _distribution(lambda_away)
    total = [0.0] * 81
    for h, ph in enumerate(home):
        for a, pa in enumerate(away):
            total[h + a] += ph * pa
    if float(line).is_integer():
        push = total[int(line)]
        over = sum(total[int(line) + 1:])
        under = sum(total[:int(line)])
    else:
        push = 0.0
        over = sum(total[int(line) + 1:])
        under = sum(total[:int(line) + 1])
    return {
        "market": market,
        "expected_counts": {"home": lambda_home, "away": lambda_away, "total": lambda_home + lambda_away},
        "line": line,
        "over": over,
        "under": under,
        "push": push,
        "model": "independent_poisson_count_baseline",
        "warning": "Cálculo base. No es pronóstico de partido sin tasas entrenadas con estadísticas históricas verificadas.",
    }
