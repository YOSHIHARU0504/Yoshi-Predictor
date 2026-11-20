"""Metrics helpers for probability forecasts."""
from __future__ import annotations

from typing import Iterable


def classification_metrics(predictions: Iterable[dict]) -> dict:
    rows = list(predictions)
    if not rows:
        return {"count": 0, "accuracy": None, "brier_score": None, "log_loss": None}
    accuracy = sum(row["predicted"] == row["actual"] for row in rows) / len(rows)
    brier = 0.0
    log_loss = 0.0
    eps = 1e-15
    for row in rows:
        probs = row["probabilities"]
        actual = row["actual"]
        brier += sum((probs[k] - float(k == actual)) ** 2 for k in ("home", "draw", "away"))
        log_loss -= __import__("math").log(max(eps, probs[actual]))
    return {
        "count": len(rows),
        "accuracy": accuracy,
        "brier_score": brier / len(rows),
        "log_loss": log_loss / len(rows),
    }
