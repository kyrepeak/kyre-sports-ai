"""Kyre Sports API — NFL Game Totals Page 2 display context V2.

Owns external provider collection for matchup history (nflverse) and official NFL
injury availability. The application-facing Streamlit page consumes only this
Kyre Sports API contract. New context is descriptive only with 0.0 model influence.
"""
from __future__ import annotations

from html import unescape
import re
from typing import Any, Mapping

import pandas as pd
import requests
from fastapi import APIRouter, Query

from nfl_game_totals_page2_context_v2 import (
    availability_empty,
    history_empty,
    normalize_availability,
    normalize_matchup_history,
)
from sports_api import nfl_data_nflverse_v1 as nflverse
from sports_api.nfl_rushing_yards_page2_enrichment_v1 import (
    NFL_INJURY_URL,
    TEAM_NAMES,
    parse_official_nfl_injury_html,
)

SCHEMA_VERSION = "nfl_game_totals_page2_context_v2"
GATEWAY = "KYRE_SPORTS_API"
router = APIRouter(prefix="/api/v1/nfl/game-totals/page2-context", tags=["nfl-game-totals-page2"])
_TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_TEAM_ALIASES = {code: (full, full.split()[-1]) for code, full in TEAM_NAMES.items()}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _abbr(value: Any) -> str:
    return nflverse.canonical_team_abbr(value)


def _nearest_table_team(prefix_html: str, targets: set[str]) -> str:
    visible = re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", str(prefix_html or "")))).casefold()
    best_code, best_position = "", -1
    for code in targets:
        for alias in _TEAM_ALIASES.get(code, ()):
            for match in re.finditer(r"(?<![a-z0-9])" + re.escape(alias.casefold()) + r"(?![a-z0-9])", visible):
                if match.start() > best_position:
                    best_code, best_position = code, match.start()
    return best_code


def parse_targeted_official_injury_html(html: str, team_codes: set[str] | list[str] | tuple[str, ...]) -> dict[str, dict[str, Any]]:
    targets = {_abbr(code) for code in team_codes if _abbr(code)}
    if not targets:
        return {}
    raw = str(html or "")
    tables = list(_TABLE_RE.finditer(raw))
    out: dict[str, dict[str, Any]] = {}
    seen: dict[str, set[tuple[str, str]]] = {code: set() for code in targets}
    previous_end = 0
    for match in tables:
        between = raw[previous_end:match.start()]
        previous_end = match.end()
        code = _nearest_table_team(between, targets)
        if not code:
            continue
        parsed = parse_official_nfl_injury_html(f"<div>{TEAM_NAMES.get(code, code)}</div>{match.group(0)}")
        team = parsed.get(code) if isinstance(parsed.get(code), Mapping) else {}
        bucket = out.setdefault(code, {"verified": True, "rows": []})
        for row in team.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            identity = (_text(row.get("player_name")).casefold(), _text(row.get("position")).upper())
            if not identity[0] or identity in seen[code]:
                continue
            seen[code].add(identity)
            bucket["rows"].append(dict(row))
    return out


def _load_history_frame() -> pd.DataFrame | None:
    try:
        return nflverse._load_games_csv()
    except Exception:
        return None


def _load_injury_html() -> str:
    response = requests.get(NFL_INJURY_URL, timeout=10, headers={"User-Agent": "KyreSportsAPI/1.0", "Accept": "text/html"})
    response.raise_for_status()
    return response.text


def build_page2_context(
    *,
    away_abbr: str,
    home_abbr: str,
    history_limit: int = 3,
    availability_limit: int = 2,
    history_frame: pd.DataFrame | None = None,
    injury_html: str | None = None,
) -> dict[str, Any]:
    away = _abbr(away_abbr); home = _abbr(home_abbr)
    if not away or not home or away == home:
        history = history_empty("MATCHUP_IDENTITY_UNAVAILABLE", "Exact team identity is unavailable.")
        availability = availability_empty("Exact team identity is unavailable.")
    else:
        frame = history_frame if history_frame is not None else _load_history_frame()
        history = normalize_matchup_history(frame, away, home, limit=history_limit)
        try:
            html = _load_injury_html() if injury_html is None else injury_html
            report = parse_targeted_official_injury_html(html, {away, home})
            availability = normalize_availability(report, away, home, limit_per_team=availability_limit)
        except Exception as exc:
            availability = availability_empty(f"Official NFL injury report unavailable ({type(exc).__name__}).")
    return {
        "schema_version": SCHEMA_VERSION,
        "gateway": GATEWAY,
        "ready": history.get("ready") is True or availability.get("ready") is True,
        "identity": {"away_abbr": away, "home_abbr": home},
        "history": history,
        "availability": availability,
        "semantics": {
            "history_model_influence": 0.0,
            "availability_model_influence": 0.0,
            "sportsbook_projection_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


@router.get("")
def page2_context(
    away: str = Query(..., min_length=2, max_length=3),
    home: str = Query(..., min_length=2, max_length=3),
    history_limit: int = Query(3, ge=1, le=5),
    availability_limit: int = Query(2, ge=1, le=5),
) -> dict[str, Any]:
    return build_page2_context(away_abbr=away, home_abbr=home, history_limit=history_limit, availability_limit=availability_limit)


__all__ = ["GATEWAY", "SCHEMA_VERSION", "build_page2_context", "parse_targeted_official_injury_html", "router"]
