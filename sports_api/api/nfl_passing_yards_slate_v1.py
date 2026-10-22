"""Kyre Sports API — NFL Passing Yards all-starting-QB slate V1.

Application-facing contract stays inside Kyre Sports API. Underlying data is
routed through the already-certified Passing Yards source layer: NFLverse for
schedule/stats/identity, FanDuel first for the market, and the approved optional
secondary market fallback already owned by that layer. Missing data is explicit;
conflicting sportsbook lines are never averaged.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from fastapi import APIRouter, Query

from sports_api.api import nfl_passing_yards_page_v1 as base
from sports_api.collectors import nfl_fanduel_passing_yards_nflverse_v1 as market_fill

SCHEMA_VERSION = "nfl_passing_yards_simple_qb_grid_v1"
router = APIRouter(prefix="/api/v1/nfl/passing-yards/slate", tags=["nfl-passing-yards-slate"])


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _schedule_games(target_date: str | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    legacy = base._legacy
    frame = legacy._load_games_csv()
    if frame is None or frame.empty:
        return None, []
    rows = frame.copy()
    if "game_type" in rows.columns:
        rows = rows[rows["game_type"].astype(str).str.upper().eq("REG")]
    if rows.empty:
        return None, []
    rows["_date"] = rows["gameday"].astype(str).str[:10]

    if target_date:
        anchor_date = str(target_date)[:10]
        anchor_rows = rows[rows["_date"].eq(anchor_date)]
    else:
        today = datetime.now(timezone.utc).date().isoformat()
        future = rows[rows["_date"] >= today]
        if future.empty:
            return None, []
        anchor_date = str(future["_date"].min())
        anchor_rows = future[future["_date"].eq(anchor_date)]
    if anchor_rows.empty:
        return anchor_date, []

    anchor = anchor_rows.sort_values(["_date", "gametime"] if "gametime" in anchor_rows.columns else ["_date"]).iloc[0]
    season_num = _num(anchor.get("season"))
    week_num = _num(anchor.get("week"))
    if season_num is None or week_num is None:
        return anchor_date, []
    season = int(season_num)
    week = int(week_num)
    weekly = rows[
        rows["season"].map(_num).eq(float(season))
        & rows["week"].map(_num).eq(float(week))
    ].copy()
    if weekly.empty:
        return anchor_date, []

    sort_cols = ["_date"] + (["gametime"] if "gametime" in weekly.columns else [])
    games: list[dict[str, Any]] = []
    for _, row in weekly.sort_values(sort_cols).iterrows():
        away = legacy.canonical_team_abbr(row.get("away_team"))
        home = legacy.canonical_team_abbr(row.get("home_team"))
        if not away or not home:
            continue
        game_season = _num(row.get("season"))
        game_week = _num(row.get("week"))
        if game_season is None:
            continue
        game_date = str(row.get("_date"))
        games.append({
            "game_id": legacy._canonical_game_id(row.get("game_id")),
            "source_game_id": legacy._safe(row.get("game_id")),
            "date": game_date,
            "season": int(game_season),
            "week": int(game_week) if game_week is not None else None,
            "away": away,
            "home": home,
            "away_team_id": legacy._canonical_team_id(away),
            "home_team_id": legacy._canonical_team_id(home),
            "away_name": legacy.TEAM_NAMES.get(away, away),
            "home_name": legacy.TEAM_NAMES.get(home, home),
            "away_logo_url": legacy._official_team_logo_url(away),
            "home_logo_url": legacy._official_team_logo_url(home),
            "kickoff": legacy._safe(row.get("gametime")),
        })
    return anchor_date, games


def _season_context(season: int, cutoff: str) -> dict[str, Any]:
    legacy = base._legacy
    frame = legacy._completed_before(legacy._load_pbp(season), cutoff)
    return {
        "frame": frame,
        "current_rows": legacy._qb_game_rows(frame),
        "defenses": legacy._defense_profiles(frame),
        "history": legacy._history_rows(list(range(max(1999, season - 2), season + 1)), cutoff),
    }


def _collect_market_observations(game: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        direct = market_fill.collect_fanduel_game_markets(game)
    except Exception:
        direct = []
    if direct:
        return direct
    return base.collect_market_observations(game)


def _name_key(value: Any) -> tuple[str, str] | None:
    tokens = [token.lower() for token in re.findall(r"[A-Za-z]+", _text(value))]
    while tokens and tokens[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        tokens.pop()
    if len(tokens) < 2:
        return None
    return tokens[0][0], tokens[-1]


def _current_rows_for_market_qb(team: str, current_rows: list[dict[str, Any]], observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    market_names = {
        _text(row.get("player_name"))
        for row in observations
        if _text(row.get("team_abbr")).upper() == _text(team).upper() and _text(row.get("player_name"))
    }
    if len(market_names) != 1:
        return current_rows
    target_key = _name_key(next(iter(market_names)))
    if target_key is None:
        return current_rows
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in current_rows:
        if _text(row.get("team")).upper() != _text(team).upper():
            continue
        player_id = _text(row.get("player_source_id"))
        qb_name = _text(row.get("qb_name"))
        if not player_id or not qb_name or _name_key(qb_name) != target_key:
            continue
        candidates.setdefault((player_id, qb_name), []).append(row)
    if len(candidates) != 1:
        return current_rows
    (player_id, qb_name), _matches = next(iter(candidates.items()))
    return [
        row for row in current_rows
        if _text(row.get("team")).upper() != _text(team).upper()
        or (_text(row.get("player_source_id")) == player_id and _text(row.get("qb_name")) == qb_name)
    ]


def _observations_for_player(player: dict[str, Any], observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    team = _text(player.get("team_abbr")).upper()
    qb_name = _text(player.get("qb_name"))
    target_key = _name_key(qb_name)
    normalized: list[dict[str, Any]] = []
    for raw in observations:
        row = dict(raw)
        source_name = _text(row.get("player_name"))
        if (
            team
            and target_key is not None
            and _text(row.get("team_abbr")).upper() == team
            and _name_key(source_name) == target_key
        ):
            row["source_player_name"] = source_name
            row["player_name"] = qb_name
        normalized.append(row)
    return normalized


def _enrich_player(player: dict[str, Any], *, game: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    projection = (player.get("context_projection") or {}).get("context_projection_yards")
    player_observations = _observations_for_player(player, observations)
    snapshot = base.build_market_snapshot(player_observations, qb_name=_text(player.get("qb_name")), projection_yards=projection)
    player = dict(player)
    player["market"] = snapshot if snapshot.get("ready") else None
    player["market_evaluation"] = base._market_evaluation(player, snapshot)
    player["availability"] = {
        "verified": False,
        "status": "CHECK",
        "reason": "Official injury/availability data not verified for this request",
    }
    schedule = base._schedule_environment(game)
    player["game_environment"] = base.build_game_environment(schedule, side=_text(player.get("side")))
    player["page1_decision_support"] = base.build_page1_decision_support(player, game_date=_text(game.get("date")))
    return player


def build_game_bundles(target_date: str | None = None) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    resolved_date, games = _schedule_games(target_date)
    provenance = {
        "provider": "NFLverse",
        "market_primary": "FanDuel",
        "market_secondary": "The Odds API when configured and needed",
    }
    if not resolved_date or not games:
        return resolved_date, [], provenance
    contexts: dict[tuple[int, str], dict[str, Any]] = {}
    bundles: list[dict[str, Any]] = []
    for game in games:
        season = int(game["season"])
        game_date = _text(game.get("date")) or str(resolved_date or "")
        context_key = (season, game_date)
        if context_key not in contexts:
            try:
                contexts[context_key] = _season_context(season, game_date)
            except Exception:
                contexts[context_key] = {"frame": None, "current_rows": [], "defenses": {}, "history": []}
        ctx = contexts[context_key]
        frame = ctx.get("frame")
        if frame is None:
            continue
        observations = _collect_market_observations(game)
        players: list[dict[str, Any]] = []
        for team, opponent, side in ((game["away"], game["home"], "away"), (game["home"], game["away"], "home")):
            defense = (ctx.get("defenses") or {}).get(opponent) or {
                "team_id": base._legacy._canonical_team_id(opponent),
                "team_abbr": opponent,
                "team_name": base._legacy.TEAM_NAMES.get(opponent, opponent),
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
            current_rows = _current_rows_for_market_qb(team, ctx.get("current_rows") or [], observations)
            row = base._legacy._player_bundle(
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
                players.append(_enrich_player(row, game=game, observations=observations))
        bundles.append({"game": game, "players": players})
    return resolved_date, bundles, provenance


def build_public_qb_card(game: dict[str, Any], player: dict[str, Any]) -> dict[str, Any]:
    visuals = player.get("identity_visuals") or {}
    market = player.get("market") or {}
    evaluation = player.get("market_evaluation") or {}
    projection = _num((player.get("context_projection") or {}).get("context_projection_yards"))
    line = _num(market.get("line")) if market.get("ready") else None
    over = _num(evaluation.get("model_over_probability")) if evaluation.get("ready") else None
    under = _num(evaluation.get("model_under_probability")) if evaluation.get("ready") else None
    if line is not None and over is not None and under is not None:
        favored = "OVER" if over > under else ("UNDER" if under > over else "NO_STRONG_SIDE")
    else:
        favored = "NO_STRONG_SIDE"
    edge = round(projection - line, 1) if projection is not None and line is not None else None
    confidence = _text((player.get("context_projection") or {}).get("confidence") or (player.get("distribution") or {}).get("confidence") or "CHECK").upper()
    market_status = "VERIFIED" if line is not None and _text(market.get("sportsbook")) else "NOT_AVAILABLE"
    essential = [
        _text(player.get("player_id")), _text(player.get("qb_name")), _text(player.get("team_abbr")),
        _text(player.get("opponent_abbr")), _text(game.get("game_id")), _text(game.get("kickoff")),
        projection, line, over, under,
    ]
    data_status = "VERIFIED" if all(value is not None and value != "" for value in essential) else "PARTIAL"
    return {
        "player_id": _text(player.get("player_id")),
        "qb_name": _text(player.get("qb_name")),
        "team_id": _text(player.get("team_id")),
        "team_abbr": _text(player.get("team_abbr")),
        "team_name": _text(player.get("team_name")),
        "opponent_team_id": _text(player.get("opponent_team_id")),
        "opponent_abbr": _text(player.get("opponent_abbr")),
        "game_id": _text(game.get("game_id")),
        "game_date": _text(game.get("date")),
        "game_time": _text(game.get("kickoff")),
        "home_away": _text(player.get("side")).upper(),
        "headshot_url": _text(visuals.get("headshot_url")) or None,
        "team_logo_url": _text(visuals.get("team_logo_url")) or None,
        "opponent_logo_url": _text(visuals.get("opponent_logo_url")) or None,
        "identity_status": "VERIFIED" if visuals.get("identity_verified") is True else "CHECK",
        "starter_status": "MARKET_LISTED" if market_status == "VERIFIED" else "PROJECTED_RECENT_USAGE",
        "market": {
            "status": market_status,
            "sportsbook": _text(market.get("sportsbook")) or None,
            "market": "Passing Yards",
            "line": line,
            "over_odds": _num(market.get("over_odds")) if market_status == "VERIFIED" else None,
            "under_odds": _num(market.get("under_odds")) if market_status == "VERIFIED" else None,
            "timestamp": _text(market.get("source_timestamp")) or None,
        },
        "projection_yards": projection,
        "edge_yards": edge,
        "over_probability": over,
        "under_probability": under,
        "favored_side": favored,
        "confidence": confidence,
        "data_status": data_status,
        "detail": player,
    }


def build_slate_bundle(target_date: str | None = None) -> dict[str, Any]:
    captured = datetime.now(timezone.utc).isoformat()
    resolved_date, bundles, provenance = build_game_bundles(target_date)
    cards: list[dict[str, Any]] = []
    for bundle in bundles:
        game = bundle.get("game") or {}
        for player in bundle.get("players") or []:
            cards.append(build_public_qb_card(game, player))
    cards.sort(key=lambda row: (_text(row.get("game_date")), _text(row.get("game_time")), _text(row.get("qb_name"))))
    game_ids = {_text((bundle.get("game") or {}).get("game_id")) for bundle in bundles if _text((bundle.get("game") or {}).get("game_id"))}
    game_dates = sorted({_text((bundle.get("game") or {}).get("date")) for bundle in bundles if _text((bundle.get("game") or {}).get("date"))})
    weeks = sorted({int((bundle.get("game") or {}).get("week")) for bundle in bundles if (bundle.get("game") or {}).get("week") is not None})
    return {
        "ready": bool(cards),
        "schema_version": SCHEMA_VERSION,
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "source_timestamp": captured,
        "game_date": resolved_date,
        "week": weeks[0] if len(weeks) == 1 else None,
        "slate_start": game_dates[0] if game_dates else resolved_date,
        "slate_end": game_dates[-1] if game_dates else resolved_date,
        "game_count": len(game_ids),
        "quarterback_count": len(cards),
        "quarterbacks": cards,
        "provenance": provenance,
        "routing": {
            "gateway": "Kyre Sports API",
            "canonical_ids": True,
            "schedule_stats_identity": "NFLverse",
            "market_primary": "FanDuel",
            "market_secondary": "The Odds API only when needed/configured",
            "sportsbook_line_averaging": False,
            "missing_to_zero": False,
            "no_guessing": True,
            "provider_failure_fallback": True,
        },
        "reason": None if cards else "No verified starting-quarterback cards available for requested slate",
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {"ready": True, "schema_version": SCHEMA_VERSION, "gateway": "Kyre Sports API"}


@router.get("")
def slate(date: str | None = Query(default=None)) -> dict[str, Any]:
    return build_slate_bundle(date)