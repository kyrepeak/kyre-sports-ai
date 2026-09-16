"""Presentation-only grade translation for NFL Passing Yards.

This module does not calculate matchup quality. It only translates directional
labels that already exist in certified Passing Yards HTML into the compact
FAVORABLE / MEDIUM / TOUGH vocabulary used by the dashboard.
"""
from __future__ import annotations

from html import unescape
import re
from typing import Any

GRADE_FAVORABLE = "FAVORABLE"
GRADE_MEDIUM = "MEDIUM"
GRADE_TOUGH = "TOUGH"

_TONE_BY_GRADE = {
    GRADE_FAVORABLE: "green",
    GRADE_MEDIUM: "amber",
    GRADE_TOUGH: "red",
}


def _visible_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value if value is not None else ""))
    text = unescape(text)
    return " ".join(text.upper().split())


def _result(label: str) -> dict[str, str]:
    return {"label": label, "tone": _TONE_BY_GRADE[label]}


def grade_certified_html(html: Any, *, surface: str = "evidence") -> dict[str, str]:
    """Translate existing certified direction only; unknown evidence is MEDIUM."""
    text = _visible_text(html)
    kind = str(surface or "evidence").strip().lower()

    if kind == "market":
        if "LEAN OVER" in text:
            return _result(GRADE_FAVORABLE)
        if "LEAN UNDER" in text:
            return _result(GRADE_TOUGH)
        return _result(GRADE_MEDIUM)

    if kind == "projection":
        if "WITHHELD" in text:
            return _result(GRADE_TOUGH)
        if "FAVORABLE" in text or "GREEN" in text:
            return _result(GRADE_FAVORABLE)
        if "TOUGH" in text or "HURT" in text:
            return _result(GRADE_TOUGH)
        return _result(GRADE_MEDIUM)

    if "FAVORABLE" in text or re.search(r"\bHELP\b", text):
        return _result(GRADE_FAVORABLE)
    if "TOUGH" in text or re.search(r"\bHURT\b", text):
        return _result(GRADE_TOUGH)
    return _result(GRADE_MEDIUM)


__all__ = [
    "GRADE_FAVORABLE",
    "GRADE_MEDIUM",
    "GRADE_TOUGH",
    "grade_certified_html",
]
