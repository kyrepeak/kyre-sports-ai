"""Decision-first NFL Rushing Yards Page 2 detail service.

This is an additive Kyre Sports API endpoint. Page 1 remains on the frozen
league-wide slate; expensive advanced rushing derivations run only when a
canonical RB detail page is opened.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math
from statistics import median
from typing import Any, Mapping

import pandas as pd
import requests
from fastapi import APIRouter, Query

import sports_api.api.nfl_rushing_yards_slate_v1 as slate
from sports_api.nfl_data_nflverse_v1 import canonical_team_abbr

router = APIRouter(prefix="/api/v1/nfl/rushing-yards/detail", tags=["nfl-rushing-yards-detail"])
SCHEMA_VERSION = "nfl_rushing_yards_page2_command_center_v2"
SERVICE = "kyre-sports-api"
GATEWAY = "Kyre Sports API"

DETAIL_PBP_COLUMNS = (
    "game_id", "season", "season_type", "week", "game_date", "posteam", "defteam", "no_play",
    "rusher_player_id", "rusher_player_name", "rush_attempt", "rushing_yards", "rush_touchdown",
    "epa", "success", "yardline_100", "qtr", "score_differential",
)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _avg(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(float(value), digits)


def _sum_optional(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_num(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


@lru_cache(maxsize=4)
def _load_detail_pbp(season: int) -> pd.DataFrame:
    response = requests.get(slate.PBP_URL.format(season=int(season)), timeout=slate.REQUEST_TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(
        BytesIO(response.content),
        compression="gzip",
        usecols=lambda name: name in DETAIL_PBP_COLUMNS,
        low_memory=False,
    )


def _completed_rush_rows(frame: pd.DataFrame, cutoff_day: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    required = {"game_id", "posteam", "defteam", "rusher_player_id", "rush_attempt", "rushing_yards"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()
    rows = frame.copy()
    if "season_type" in rows.columns:
        rows = rows[rows["season_type"].astype(str).str.upper().eq("REG")]
    if "game_date" in rows.columns:
        rows = rows[rows["game_date"].astype(str).str[:10] < str(cutoff_day)[:10]]
    if "no_play" in rows.columns:
        rows = rows[~pd.to_numeric(rows["no_play"], errors="coerce").eq(1.0)]
    rows = rows[pd.to_numeric(rows["rush_attempt"], errors="coerce").eq(1.0)]
    return rows.copy()


def _series(group: pd.DataFrame, key: str) -> pd.Series | None:
    if key not in group.columns:
        return None
    values = pd.to_numeric(group[key], errors="coerce")
    return values if values.notna().any() else None


def _player_game_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    required = {"game_id", "posteam", "defteam", "rusher_player_id", "rusher_player_name", "rush_attempt", "rushing_yards"}
    if not required.issubset(frame.columns):
        return []
    grouped = frame.dropna(subset=["game_id", "posteam", "defteam", "rusher_player_id"]).groupby(
        ["game_id", "posteam", "defteam", "rusher_player_id", "rusher_player_name"], dropna=True
    )
    out: list[dict[str, Any]] = []
    for (game_id, team, opponent, source_id, name), group in grouped:
        attempts = int(pd.to_numeric(group["rush_attempt"], errors="coerce").eq(1.0).sum())
        yards_series = pd.to_numeric(group["rushing_yards"], errors="coerce")
        if attempts <= 0 or not yards_series.notna().any():
            continue
        yards = float(yards_series.sum(min_count=1))
        epa = _series(group, "epa")
        success = _series(group, "success")
        yardline = _series(group, "yardline_100")
        qtr = _series(group, "qtr")
        score = _series(group, "score_differential")
        advanced_available = any(series is not None for series in (epa, success, yardline, qtr, score))
        out.append({
            "source_game_id": _text(game_id),
            "game_date": _text(group["game_date"].iloc[0])[:10] if "game_date" in group.columns else "",
            "week": int(_num(group["week"].iloc[0]) or 0) if "week" in group.columns else 0,
            "team_abbr": canonical_team_abbr(team),
            "opponent_abbr": canonical_team_abbr(opponent),
            "player_source_id": _text(source_id),
            "player_name": _text(name),
            "attempts": attempts,
            "rushing_yards": yards,
            "rushing_touchdowns": int(pd.to_numeric(group.get("rush_touchdown", pd.Series(dtype=float)), errors="coerce").eq(1.0).sum()),
            "explosive_runs": int(yards_series.ge(10).sum()),
            "stuffed_runs": int(yards_series.le(0).sum()),
            "successful_runs": int(success.eq(1.0).sum()) if success is not None else None,
            "rush_epa": float(epa.sum()) if epa is not None else None,
            "red_zone_attempts": int(yardline.le(20).sum()) if yardline is not None else None,
            "goal_line_attempts": int(yardline.le(5).sum()) if yardline is not None else None,
            "fourth_quarter_attempts": int(qtr.eq(4).sum()) if qtr is not None else None,
            "leading_attempts": int(score.gt(0).sum()) if score is not None else None,
            "trailing_attempts": int(score.lt(0).sum()) if score is not None else None,
            "advanced_sample_available": advanced_available,
        })
    out.sort(key=lambda row: (row.get("game_date") or "", row.get("source_game_id") or ""))
    return out


def build_workload_intelligence(player_source_id: str, team: str, game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    player_rows = [row for row in game_rows if _text(row.get("player_source_id")) == _text(player_source_id)]
    player_rows.sort(key=lambda row: (row.get("game_date") or "", row.get("source_game_id") or ""))
    team_rows = [row for row in game_rows if canonical_team_abbr(row.get("team_abbr")) == canonical_team_abbr(team)]
    attempts = [float(_num(row.get("attempts")) or 0.0) for row in player_rows]
    total_player_attempts = sum(attempts)
    total_team_attempts = sum(float(_num(row.get("attempts")) or 0.0) for row in team_rows)
    season = _avg(attempts)
    l3 = _avg(attempts[-3:])
    l5 = _avg(attempts[-5:])
    trend = "NO_QUALIFYING_GAMES"
    if season is not None and l3 is not None:
        delta = l3 - (l5 if l5 is not None else season)
        trend = "RISING" if delta >= 1.0 else "FALLING" if delta <= -1.0 else "STABLE"
    return {
        "status": "VERIFIED_DERIVED" if player_rows else "NO_QUALIFYING_GAMES",
        "sample_games": len(player_rows),
        "season_carries_per_game": _round(season),
        "l3_carries_per_game": _round(l3),
        "l5_carries_per_game": _round(l5),
        "team_rush_attempt_share": _round(total_player_attempts / total_team_attempts) if total_team_attempts > 0 else None,
        "workload_trend": trend,
        "red_zone_carries": _sum_optional(player_rows, "red_zone_attempts"),
        "goal_line_carries": _sum_optional(player_rows, "goal_line_attempts"),
        "fourth_quarter_carries": _sum_optional(player_rows, "fourth_quarter_attempts"),
        "leading_carries": _sum_optional(player_rows, "leading_attempts"),
        "trailing_carries": _sum_optional(player_rows, "trailing_attempts"),
    }


def build_recent_form(player_source_id: str, game_rows: list[dict[str, Any]], market: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in game_rows if _text(row.get("player_source_id")) == _text(player_source_id)]
    rows.sort(key=lambda row: (row.get("game_date") or "", row.get("source_game_id") or ""))
    yards = [float(value) for value in (_num(row.get("rushing_yards")) for row in rows) if value is not None]
    line = _num(market.get("line")) if _text(market.get("status")) == "VERIFIED" else None
    hit_rate = (sum(1 for value in yards if value > line) / len(yards)) if line is not None and yards else None
    return {
        "status": "VERIFIED_DERIVED" if yards else "NO_QUALIFYING_GAMES",
        "sample_games": len(yards),
        "season_average": _round(_avg(yards)),
        "l3_average": _round(_avg(yards[-3:])),
        "l5_average": _round(_avg(yards[-5:])),
        "median": _round(float(median(yards))) if yards else None,
        "floor": min(yards) if yards else None,
        "ceiling": max(yards) if yards else None,
        "current_line_hit_rate": _round(hit_rate),
        "hit_rate_status": "VERIFIED" if hit_rate is not None else (_text(market.get("status")) or "MARKET_NOT_POSTED"),
        "games_detail": list(reversed(rows[-10:])),
    }


def build_defense_profiles(game_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_team: dict[str, list[dict[str, Any]]] = {}
    for row in game_rows:
        defense = canonical_team_abbr(row.get("opponent_abbr"))
        if defense:
            by_team.setdefault(defense, []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for defense, rows in by_team.items():
        game_ids = {str(row.get("source_game_id")) for row in rows if row.get("source_game_id")}
        games = len(game_ids)
        attempts = sum(float(_num(row.get("attempts")) or 0.0) for row in rows)
        yards = sum(float(_num(row.get("rushing_yards")) or 0.0) for row in rows)
        explosive = _sum_optional(rows, "explosive_runs")
        stuffed = _sum_optional(rows, "stuffed_runs")
        successful = _sum_optional(rows, "successful_runs")
        epa = _sum_optional(rows, "rush_epa")
        out[defense] = {
            "team_abbr": defense,
            "games": games,
            "rush_attempts_allowed_per_game": _round(attempts / games) if games else None,
            "rush_yards_allowed_per_game": _round(yards / games) if games else None,
            "yards_per_carry_allowed": _round(yards / attempts) if attempts > 0 else None,
            "explosive_run_rate_allowed": _round(explosive / attempts) if explosive is not None and attempts > 0 else None,
            "stuff_rate": _round(stuffed / attempts) if stuffed is not None and attempts > 0 else None,
            "success_rate_allowed": _round(successful / attempts) if successful is not None and attempts > 0 else None,
            "rush_epa_allowed_per_attempt": _round(epa / attempts) if epa is not None and attempts > 0 else None,
        }
    ranking = sorted(
        ((team, row["rush_yards_allowed_per_game"]) for team, row in out.items() if row.get("rush_yards_allowed_per_game") is not None),
        key=lambda item: float(item[1]),
    )
    ranks = {team: idx + 1 for idx, (team, _value) in enumerate(ranking)}
    for team, row in out.items():
        rank = ranks.get(team)
        row["rank"] = rank
        row["grade"] = "TOUGH" if rank and rank <= 8 else "FAVORABLE" if rank and rank >= 21 else "MEDIUM" if rank else "CHECK"
    return out


def build_comparable_matchups(player_source_id: str, opponent: str, game_rows: list[dict[str, Any]], defenses: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    target_grade = _text((defenses.get(canonical_team_abbr(opponent)) or {}).get("grade"))
    if not target_grade or target_grade == "CHECK":
        return {"status": "NO_COMPARABLE_MATCHUPS", "target_grade": target_grade or None, "games": 0, "games_detail": []}
    rows = [
        row for row in game_rows
        if _text(row.get("player_source_id")) == _text(player_source_id)
        and canonical_team_abbr(row.get("opponent_abbr")) != canonical_team_abbr(opponent)
        and _text((defenses.get(canonical_team_abbr(row.get("opponent_abbr"))) or {}).get("grade")) == target_grade
    ]
    rows.sort(key=lambda row: (row.get("game_date") or "", row.get("source_game_id") or ""))
    yards = [float(value) for value in (_num(row.get("rushing_yards")) for row in rows) if value is not None]
    return {
        "status": "VERIFIED" if rows else "NO_COMPARABLE_MATCHUPS",
        "target_grade": target_grade,
        "games": len(rows),
        "average_rushing_yards": _round(_avg(yards)),
        "games_detail": list(reversed(rows[-5:])),
    }


def build_advanced_efficiency(player_source_id: str, game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in game_rows if _text(row.get("player_source_id")) == _text(player_source_id)]
    attempts = sum(float(_num(row.get("attempts")) or 0.0) for row in rows)
    explosive = _sum_optional(rows, "explosive_runs")
    stuffed = _sum_optional(rows, "stuffed_runs")
    successful = _sum_optional(rows, "successful_runs")
    epa = _sum_optional(rows, "rush_epa")
    red_zone = _sum_optional(rows, "red_zone_attempts")
    goal_line = _sum_optional(rows, "goal_line_attempts")
    advanced_available = any(row.get("advanced_sample_available") is True for row in rows)
    return {
        "status": "VERIFIED_DERIVED" if advanced_available and attempts > 0 else "ADVANCED_SAMPLE_NOT_VERIFIED",
        "attempts": attempts if attempts > 0 else None,
        "explosive_run_rate": _round(explosive / attempts) if explosive is not None and attempts > 0 else None,
        "stuff_rate": _round(stuffed / attempts) if stuffed is not None and attempts > 0 else None,
        "success_rate": _round(successful / attempts) if successful is not None and attempts > 0 else None,
        "rush_epa_per_attempt": _round(epa / attempts) if epa is not None and attempts > 0 else None,
        "red_zone_carries": red_zone,
        "goal_line_carries": goal_line,
    }


def build_game_script(player_source_id: str, team: str, game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    player_rows = [row for row in game_rows if _text(row.get("player_source_id")) == _text(player_source_id)]
    team_rows = [row for row in game_rows if canonical_team_abbr(row.get("team_abbr")) == canonical_team_abbr(team)]
    game_ids = {str(row.get("source_game_id")) for row in team_rows if row.get("source_game_id")}
    team_attempts = sum(float(_num(row.get("attempts")) or 0.0) for row in team_rows)
    player_attempts = sum(float(_num(row.get("attempts")) or 0.0) for row in player_rows)
    leading = _sum_optional(player_rows, "leading_attempts")
    trailing = _sum_optional(player_rows, "trailing_attempts")
    fourth = _sum_optional(player_rows, "fourth_quarter_attempts")
    return {
        "status": "VERIFIED_DERIVED" if game_ids else "NO_QUALIFYING_GAMES",
        "team_rush_attempts_per_game": _round(team_attempts / len(game_ids)) if game_ids else None,
        "player_leading_carry_share": _round(leading / player_attempts) if leading is not None and player_attempts > 0 else None,
        "player_trailing_carry_share": _round(trailing / player_attempts) if trailing is not None and player_attempts > 0 else None,
        "player_fourth_quarter_carry_share": _round(fourth / player_attempts) if fourth is not None and player_attempts > 0 else None,
        "spread_status": "GAME_SPREAD_NOT_VERIFIED",
        "total_status": "GAME_TOTAL_NOT_VERIFIED",
        "weather_status": "WEATHER_VERIFICATION_PENDING",
    }


def build_page2_detail_blocks(
    *,
    player: Mapping[str, Any],
    opponent: str,
    game_rows: list[dict[str, Any]],
    defenses: Mapping[str, Mapping[str, Any]],
    market: Mapping[str, Any],
    projection: Mapping[str, Any],
    over_probability: float | None,
    under_probability: float | None,
    favored_side: str,
    confidence: str,
) -> dict[str, Any]:
    source_id = _text(player.get("player_source_id"))
    team = canonical_team_abbr(player.get("team_abbr"))
    workload = build_workload_intelligence(source_id, team, game_rows)
    recent = build_recent_form(source_id, game_rows, market)
    advanced = build_advanced_efficiency(source_id, game_rows)
    comparable = build_comparable_matchups(source_id, opponent, game_rows, defenses)
    script = build_game_script(source_id, team, game_rows)
    line = _num(market.get("line")) if _text(market.get("status")) == "VERIFIED" else None
    projected = _num(projection.get("projection_yards")) if projection.get("ready") is True else None
    edge = projected - line if projected is not None and line is not None else None
    side = _text(favored_side).upper() or "WAIT"
    probability = over_probability if side == "OVER" else under_probability if side == "UNDER" else None
    decision = {
        "status": "VERIFIED_DECISION" if edge is not None and probability is not None else "MARKET_PENDING",
        "side": side if edge is not None else "WAIT",
        "probability": probability if edge is not None else None,
        "confidence": confidence if edge is not None else "MARKET PENDING",
        "line": line,
        "projection": projected,
        "edge": edge,
        "expected_carries": _num(projection.get("expected_carries")),
        "expected_ypc": _num(projection.get("expected_yards_per_carry")),
    }
    market_intelligence = {
        "status": _text(market.get("status")) or "MARKET_NOT_POSTED",
        "sportsbook": market.get("sportsbook"),
        "current_line": line,
        "over_odds": market.get("over_odds") if line is not None else None,
        "under_odds": market.get("under_odds") if line is not None else None,
        "market_timestamp": market.get("timestamp"),
        "opening_line": None,
        "opening_line_status": "OPENING_LINE_NOT_CAPTURED",
        "movement": None,
        "movement_status": "MOVEMENT_HISTORY_NOT_CAPTURED",
        "sportsbook_integrity": "BOOK_SPECIFIC_RECORD",
    }
    personnel = {
        "status": "PERSONNEL_VERIFICATION_PENDING",
        "display": "Personnel verification pending",
        "offensive_line_status": "OFFENSIVE_LINE_VERIFICATION_PENDING",
        "defensive_front_status": "DEFENSIVE_FRONT_VERIFICATION_PENDING",
    }
    supporting: list[str] = []
    risks: list[str] = []
    unresolved: list[str] = []
    if edge is not None:
        relation = "above" if edge > 0 else "below" if edge < 0 else "equal to"
        supporting.append(f"Kyre projection is {abs(edge):.1f} yards {relation} the verified market line.")
    if workload.get("workload_trend") == "RISING":
        supporting.append("Verified rushing workload is rising over the recent sample.")
    defense = defenses.get(canonical_team_abbr(opponent)) or {}
    if _text(defense.get("grade")) == "FAVORABLE":
        supporting.append("Opponent run-defense grade is favorable in the verified current-season sample.")
    elif _text(defense.get("grade")) == "TOUGH":
        risks.append("Opponent run-defense grade is tough in the verified current-season sample.")
    if market_intelligence["movement_status"] != "VERIFIED":
        unresolved.append("Verified line-movement history is not captured by the current feed.")
    unresolved.append("Weather verification pending.")
    risks.append("Personnel verification is still pending.")
    summary = (
        f"Kyre leans {decision['side']} from verified workload, efficiency, and matchup evidence."
        if decision["side"] in {"OVER", "UNDER"}
        else "Kyre projection is ready, but a verified sportsbook decision is waiting on the market."
    )
    return {
        "decision": decision,
        "workload_intelligence": workload,
        "recent_form": recent,
        "game_script": script,
        "comparable_matchups": comparable,
        "advanced_efficiency": advanced,
        "market_intelligence": market_intelligence,
        "personnel": personnel,
        "final_read": {
            "supporting_factors": supporting,
            "risk_factors": risks,
            "unresolved": unresolved,
            "summary": summary,
        },
    }


def build_detail_bundle(*, player_id: str, game_id: str, target_date: str | None = None) -> dict[str, Any]:
    slate_payload = slate.build_slate_bundle(target_date=target_date)
    if slate_payload.get("ready") is not True:
        return {"ready": False, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": _text(slate_payload.get("reason")) or "Rushing slate not ready", "detail": {}}
    card = next(
        (
            row for row in (slate_payload.get("running_backs") or [])
            if _text(row.get("player_id")) == _text(player_id) and _text(row.get("game_id")) == _text(game_id)
        ),
        None,
    )
    if not isinstance(card, dict):
        return {"ready": False, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": "Canonical player/game detail not found on upcoming slate", "detail": {}}
    season = int(card.get("season") or 0)
    cutoff_day = _text(card.get("game_date"))
    try:
        frame = _completed_rush_rows(_load_detail_pbp(season), cutoff_day)
        game_rows = _player_game_rows(frame)
    except Exception as exc:
        return {"ready": False, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": f"Advanced rushing history degraded: {type(exc).__name__}", "detail": {}}
    defenses = build_defense_profiles(game_rows)
    base_detail = dict(card.get("detail") or {})
    opponent = canonical_team_abbr(card.get("opponent_abbr"))
    player = {
        "player_source_id": card.get("player_source_id"),
        "player_name": card.get("player_name"),
        "role": card.get("role"),
        "team_abbr": card.get("team_abbr"),
    }
    blocks = build_page2_detail_blocks(
        player=player,
        opponent=opponent,
        game_rows=game_rows,
        defenses=defenses,
        market=card.get("market") or {},
        projection=base_detail.get("projection") or {},
        over_probability=_num(card.get("over_probability")),
        under_probability=_num(card.get("under_probability")),
        favored_side=_text(card.get("favored_side")),
        confidence=_text(card.get("confidence")),
    )
    base_detail.update(blocks)
    base_detail["headshot_url"] = card.get("headshot_url")
    base_detail["team_logo_url"] = card.get("team_logo_url")
    base_detail["game_id"] = card.get("game_id")
    base_detail["game_time"] = card.get("game_time")
    if opponent in defenses:
        merged_defense = dict(base_detail.get("opponent_run_defense") or {})
        merged_defense.update(defenses[opponent])
        base_detail["opponent_run_defense"] = merged_defense
    lineage = dict(base_detail.get("source_lineage") or {})
    lineage.update({
        "page2_workload": "verified play-by-play derived",
        "page2_recent_form": "verified play-by-play derived",
        "page2_game_script": "verified play-by-play derived",
        "page2_comparables": "canonical opponent defense-grade derivation",
        "page2_advanced_efficiency": "verified play-by-play derived",
    })
    base_detail["source_lineage"] = lineage
    return {
        "ready": True,
        "schema_version": SCHEMA_VERSION,
        "service": SERVICE,
        "gateway": GATEWAY,
        "player_id": card.get("player_id"),
        "game_id": card.get("game_id"),
        "detail": base_detail,
    }


@router.get("")
def detail(
    player_id: str = Query(..., min_length=10),
    game_id: str = Query(..., min_length=10),
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> dict[str, Any]:
    return build_detail_bundle(player_id=player_id, game_id=game_id, target_date=date)


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "ready": True,
        "service": SERVICE,
        "gateway": GATEWAY,
        "schema_version": SCHEMA_VERSION,
        "decision_first": True,
        "page1_mutation": False,
        "sportsbook_projection_influence": 0.0,
        "semantic_empty_states": True,
    }


__all__ = [
    "DETAIL_PBP_COLUMNS", "SCHEMA_VERSION", "build_advanced_efficiency", "build_comparable_matchups",
    "build_defense_profiles", "build_detail_bundle", "build_game_script", "build_page2_detail_blocks",
    "build_recent_form", "build_workload_intelligence", "detail", "router", "status", "_player_game_rows",
]
