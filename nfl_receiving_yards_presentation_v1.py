"""Presentation-only semantic helpers for Receiving Yards player cards."""
from __future__ import annotations

from typing import Any

_ALLOWED = {"FAVORABLE", "MEDIUM", "TOUGH"}


def normalize_toughness(value: Any) -> str:
    tier = str(value or "").strip().upper()
    return tier if tier in _ALLOWED else "MEDIUM"


def semantic_role(value: Any) -> str:
    return normalize_toughness(value).lower()


__all__ = ["normalize_toughness", "semantic_role"]
