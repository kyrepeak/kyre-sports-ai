"""Exact selected-game handoff helpers for NBA Spread Page 1."""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping
import re

_GAME_KEY_RE = re.compile(r"^([A-Z]{3})@([A-Z]{3}):(\d{4}-\d{2}-\d{2})$")


def build_analysis_params(game: Mapping[str, object]) -> dict[str, str]:
    date = str(game.get("game_date_phoenix") or "").strip()
    game_key = str(game.get("game_key") or "").strip().upper()
    match = _GAME_KEY_RE.fullmatch(game_key)
    if not date or match is None or match.group(3) != date:
        return {}
    away = str(game.get("away_tricode") or match.group(1)).strip().upper()
    home = str(game.get("home_tricode") or match.group(2)).strip().upper()
    if away != match.group(1) or home != match.group(2):
        return {}
    return {"date": date, "game_id": game_key}


def apply_analysis_handoff(
    session: MutableMapping[str, object],
    query: MutableMapping[str, object],
    game: Mapping[str, object],
) -> dict[str, str]:
    params = build_analysis_params(game)
    if not params:
        return {}
    patch = {"sport": "nba", "market": "spread", **params}
    for target in (session, query):
        target.pop("player_id", None)
        for key, value in patch.items():
            target[key] = value
    return patch


__all__ = ["build_analysis_params", "apply_analysis_handoff"]
