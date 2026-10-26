"""NFL Rushing Yards Page 2 detail V4 live-acceptance successor."""
from __future__ import annotations

import re
from typing import Any, Mapping

from sports_api.api import nfl_rushing_yards_detail_v3 as base
from sports_api.nfl_rushing_yards_page2_enrichment_v1 import TEAM_NAMES
from sports_api.nfl_rushing_yards_page2_live_repair_v1 import (
    VERSION as REPAIR_VERSION,
    apply_live_acceptance_repair,
    collect_action_prop_history,
    collect_fanduel_game_lines,
    collect_official_weekly_injuries,
)

VERSION = "NFL_RUSHING_YARDS_DETAIL_V4_LIVE_ACCEPTANCE"
_BASE_BUILD = base.build_detail_bundle


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _season_week(game_id: Any) -> tuple[int, int]:
    match = re.search(r"(?:^|:)(20\d{2})_(\d{1,2})_", _text(game_id))
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _sides(detail: Mapping[str, Any]) -> tuple[str, str]:
    team = _text(detail.get("team_abbr")).upper()
    opponent = _text(detail.get("opponent_abbr")).upper()
    return (team, opponent) if _text(detail.get("home_away")).upper() == "AWAY" else (opponent, team)


def enrich_live_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(payload or {})
    if out.get("ready") is not True or not isinstance(out.get("detail"), Mapping):
        return out
    detail = dict(out["detail"])
    game_id = _text(out.get("game_id") or detail.get("game_id"))
    season, week = _season_week(game_id)
    away, home = _sides(detail)
    away_name, home_name = TEAM_NAMES.get(away, away), TEAM_NAMES.get(home, home)
    player_name = _text(detail.get("player_name"))

    diagnostics: dict[str, str] = {}
    try:
        injuries = collect_official_weekly_injuries(season=season, week=week) if season and week else {}
        diagnostics["injury_personnel"] = "AVAILABLE" if injuries else "NO_ROWS"
    except Exception as exc:
        injuries = {}
        diagnostics["injury_personnel"] = type(exc).__name__

    try:
        game_lines = collect_fanduel_game_lines(
            away_abbr=away,
            home_abbr=home,
            away_name=away_name,
            home_name=home_name,
        )
        diagnostics["game_market"] = "AVAILABLE" if game_lines else "NO_MAIN_MARKET"
    except Exception as exc:
        game_lines = {}
        diagnostics["game_market"] = type(exc).__name__

    try:
        prop_history = collect_action_prop_history(player_name=player_name) if player_name else {}
        diagnostics["prop_history"] = "AVAILABLE" if prop_history else "NO_PUBLIC_HISTORY"
    except Exception as exc:
        prop_history = {}
        diagnostics["prop_history"] = type(exc).__name__

    repaired = apply_live_acceptance_repair(
        detail,
        injury_report=injuries,
        game_lines=game_lines,
        prop_history=prop_history,
    )
    repaired["live_acceptance_diagnostics"] = diagnostics
    repaired["live_acceptance_repair_version"] = REPAIR_VERSION
    out["detail"] = repaired
    return out


def build_detail_bundle(*, player_id: str, game_id: str, target_date: str | None = None) -> dict[str, Any]:
    return enrich_live_payload(_BASE_BUILD(player_id=player_id, game_id=game_id, target_date=target_date))


base.build_detail_bundle = build_detail_bundle
router = base.router
SCHEMA_VERSION = base.SCHEMA_VERSION
SERVICE = base.SERVICE
GATEWAY = base.GATEWAY

__all__ = ["GATEWAY", "SCHEMA_VERSION", "SERVICE", "VERSION", "build_detail_bundle", "enrich_live_payload", "router"]
