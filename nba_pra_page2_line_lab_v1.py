'''NBA PRA Page 2 Line Lab — threshold exploration only.'''
from __future__ import annotations

from typing import Any

from nba_pra_page1_model_v1 import grade_market

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def line_steps(center: float, *, width: float = 10.0) -> tuple[float, ...]:
    center = round(float(center) * 2.0) / 2.0
    width = max(0.0, float(width))
    start = max(0.5, round((center - width) * 2.0) / 2.0)
    end = round((center + width) * 2.0) / 2.0
    count = int(round((end - start) * 2.0))
    return tuple(round(start + i * 0.5, 1) for i in range(count + 1))


def _score(grade: dict[str, Any]) -> tuple[float | None, str]:
    lean = str(grade.get("lean") or "PASS").upper()
    p = grade.get("over_probability")
    edge = grade.get("edge")
    if lean not in {"OVER", "UNDER"} or p is None or edge is None:
        return None, "UNAVAILABLE"
    shown = (1.0 - float(p)) if lean == "UNDER" else float(p)
    score = min(10.0, max(0.0, 5.0 + abs(float(edge)) * 0.5 + (shown - 0.5) * 10.0))
    tier = "ELITE" if score >= 9.0 else "STRONG" if score >= 7.5 else "LEAN" if score >= 6.5 else "PASS"
    return round(score, 1), tier


def evaluate_line(projection: float | None, sigma: float | None, line: float | None) -> dict[str, Any]:
    grade = grade_market(projection, line, sigma)
    p = grade.get("over_probability")
    score, tier = _score(grade)
    return {
        "projection": projection,
        "line": line,
        "edge": grade.get("edge"),
        "over_probability": p,
        "under_probability": None if p is None else 1.0 - float(p),
        "lean": grade.get("lean"),
        "confidence": grade.get("confidence"),
        "score": score,
        "tier": tier,
    }
