"""CFB Game Total Page 2 Line Lab V2.

Pure analysis helper for a user-selected total line. It consumes only the
already-owned frozen total distribution. It performs no model run, provider
request, recommendation change, market mutation, or sportsbook weighting.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

MODEL_VERSION = "CFB GAME TOTAL PAGE2 LINE LAB V2"
LINE_MIN = 0.0
LINE_MAX = 60.0
LINE_STEP = 0.5
MODEL_RERUNS = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def clamp_line(value: Any, *, fallback: float = 50.0) -> float:
    number = _number(value)
    if number is None:
        number = fallback
    number = max(LINE_MIN, min(LINE_MAX, number))
    return round(number / LINE_STEP) * LINE_STEP


def line_probabilities(distribution: Any, line: Any) -> dict[str, float] | None:
    """Return normalized Over/Under/Push mass for one frozen-distribution line."""
    threshold = _number(line)
    if threshold is None:
        return None
    if not isinstance(distribution, Sequence) or isinstance(distribution, (str, bytes)):
        return None

    over = under = push = total_mass = 0.0
    for row in distribution:
        if not isinstance(row, Mapping):
            continue
        total = _number(row.get("total"))
        probability = _number(row.get("probability"))
        if total is None or probability is None or probability < 0.0:
            continue
        total_mass += probability
        if total > threshold:
            over += probability
        elif total < threshold:
            under += probability
        else:
            push += probability

    if total_mass <= 0.0:
        return None
    return {
        "over": round(over / total_mass, 12),
        "under": round(under / total_mass, 12),
        "push": round(push / total_mass, 12),
    }


def percent(value: Any) -> str:
    number = _number(value)
    return "—" if number is None else f"{100.0 * number:.1f}%"


__all__ = [
    "LINE_MAX",
    "LINE_MIN",
    "LINE_STEP",
    "MODEL_RERUNS",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "clamp_line",
    "line_probabilities",
    "percent",
]
