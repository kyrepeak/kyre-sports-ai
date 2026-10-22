"""NFL Passing Yards slate successor overlay for Page 2 completeness.

The frozen/verified slate implementation remains the data and model owner. This
overlay reuses that implementation and only enriches each selected QB detail
with a verified current-season game log built from the same NFLverse rows that
already power the slate. Identity joins require exact source player ID + team.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_passing_yards_slate_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "sports_api.api._nfl_passing_yards_slate_v1_verified",
    _LEGACY_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Passing Yards verified slate implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)


def _game_id_context(game_id: Any, team: Any) -> tuple[int | None, str | None]:
    raw = str(game_id or "").strip()
    team_abbr = _legacy.base._legacy.canonical_team_abbr(team)
    parts = raw.split("_")
    week: int | None = None
    if len(parts) >= 2:
        try:
            week = int(parts[1])
        except (TypeError, ValueError):
            week = None
    home_away: str | None = None
    if len(parts) >= 4:
        away = _legacy.base._legacy.canonical_team_abbr(parts[-2])
        home = _legacy.base._legacy.canonical_team_abbr(parts[-1])
        if team_abbr and team_abbr == home:
            home_away = "HOME"
        elif team_abbr and team_abbr == away:
            home_away = "AWAY"
    return week, home_away


def _season_game_log_for_player(
    player: dict[str, Any],
    current_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only verified current-season QB rows for the exact canonical identity."""
    visuals = player.get("identity_visuals") or {}
    source_player_id = str(visuals.get("source_player_id") or "").strip()
    team = _legacy._text(player.get("team_abbr")).upper()
    if not source_player_id or not team:
        return []

    output: list[dict[str, Any]] = []
    for raw in current_rows:
        row = dict(raw)
        if _legacy._text(row.get("player_source_id")) != source_player_id:
            continue
        if _legacy._text(row.get("team")).upper() != team:
            continue
        game_id = _legacy._text(row.get("game_id"))
        if not game_id:
            continue
        week, home_away = _game_id_context(game_id, team)
        output.append({
            "game_id": game_id,
            "week": week,
            "home_away": home_away,
            "team": team,
            "opponent": _legacy._text(row.get("opponent")).upper() or None,
            "player_source_id": source_player_id,
            "attempts": row.get("attempts"),
            "completions": row.get("completions"),
            "passing_yards": row.get("passing_yards"),
            "pass_tds": row.get("pass_tds"),
            "interceptions": row.get("interceptions"),
        })
    output.sort(key=lambda row: (
        int(row["week"]) if row.get("week") is not None else 999,
        str(row.get("game_id") or ""),
    ))
    return output


def build_game_bundles(target_date: str | None = None):
    resolved_date, games = _legacy._schedule_games(target_date)
    provenance = {
        "provider": "NFLverse",
        "market_primary": "FanDuel",
        "market_secondary": "The Odds API when configured and needed",
        "page2_game_log": "NFLverse exact player/team identity",
    }
    if not resolved_date or not games:
        return resolved_date, [], provenance

    contexts = _legacy._prefetch_season_contexts(games)
    markets_by_game = _legacy._prefetch_market_observations(games)
    bundles: list[dict[str, Any]] = []
    for game in games:
        season = int(game["season"])
        game_date = _legacy._text(game.get("date")) or str(resolved_date or "")
        context_key = (season, game_date)
        ctx = contexts.get(context_key) or {"frame": None, "current_rows": [], "defenses": {}, "history": []}
        frame = ctx.get("frame")
        if frame is None:
            continue
        observations = markets_by_game.get(_legacy._text(game.get("game_id")), [])
        players: list[dict[str, Any]] = []
        for team, opponent, side in (
            (game["away"], game["home"], "away"),
            (game["home"], game["away"], "home"),
        ):
            defense = (ctx.get("defenses") or {}).get(opponent) or {
                "team_id": _legacy.base._legacy._canonical_team_id(opponent),
                "team_abbr": opponent,
                "team_name": _legacy.base._legacy.TEAM_NAMES.get(opponent, opponent),
                "rank": None,
                "grade": "CHECK",
                "pass_yards_allowed_per_game": None,
                "passing_attempts_allowed_per_game": None,
                "completion_pct_allowed": None,
                "yards_per_attempt_allowed": None,
                "recent3_pass_yards_allowed": None,
                "recent3_ypa_allowed": None,
                "sack_rate_generated": None,
            }
            current_rows = _legacy._current_rows_for_market_qb(
                team,
                ctx.get("current_rows") or [],
                observations,
            )
            row = _legacy.base._legacy._player_bundle(
                team=team,
                opponent=opponent,
                side=side,
                current_rows=current_rows,
                all_history=ctx.get("history") or [],
                defense=defense,
                frame=frame,
                markets=observations,
                season=season,
                week=game.get("week"),
            )
            if row:
                enriched_source = dict(row)
                enriched_source["season_game_log"] = _season_game_log_for_player(
                    enriched_source,
                    current_rows,
                )
                players.append(
                    _legacy._enrich_player(
                        enriched_source,
                        game=game,
                        observations=observations,
                    )
                )
        bundles.append({"game": game, "players": players})
    return resolved_date, bundles, provenance


# The verified endpoint resolves build_game_bundles from its module globals.
_legacy.build_game_bundles = build_game_bundles

# Expose the verified router and functions; build_slate_bundle remains the verified
# implementation and automatically consumes the enriched build_game_bundles above.
router = _legacy.router
build_slate_bundle = _legacy.build_slate_bundle
slate = _legacy.slate
status = _legacy.status

__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {
    "_season_game_log_for_player",
    "build_game_bundles",
    "build_slate_bundle",
    "router",
    "slate",
    "status",
})
