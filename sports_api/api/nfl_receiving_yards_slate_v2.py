"""Kyre Sports API NFL Receiving Yards canonical slate V2.

Owns upcoming schedule, roster/player identity, receiving summaries, opponent
pass-defense context, player-vs-opponent history, market reconciliation, and the
market-blind Receiving Yards baseline used by the V22 application page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
import math
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from fastapi import APIRouter, Query

import nfl_receiving_yards_projection_v2 as projection_model
from sports_api.collectors import nfl_fanduel_receiving_yards_nflverse_v2 as direct_book
from sports_api.nfl_data_nflverse_v1 import _load_games_csv, canonical_team_abbr

router = APIRouter(prefix="/api/v1/nfl/receiving-yards/slate-v2", tags=["nfl-receiving-yards-slate-v2"])
SCHEMA_VERSION = "nfl_receiving_yards_slate_v2"
SERVICE = "kyre-sports-api"
GATEWAY = "Kyre Sports API"
MODEL_VERSION = "NFL RECEIVING YARDS CANONICAL SLATE V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
ET = ZoneInfo("America/New_York")
REQUEST_TIMEOUT_SECONDS = 7
PLAYER_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)
WEEKLY_ROSTER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "weekly_rosters/roster_weekly_{season}.csv"
)
NFL_OFFICIAL_LOGO_BASE = "https://static.www.nfl.com/t_q-best/league/api/clubs/logos"
ACTIVE_STATUSES = frozenset({"ACT", "ACTIVE"})
RECEIVING_POSITIONS = frozenset({"WR", "TE", "RB", "FB"})
MAX_RECEIVERS_PER_TEAM = 6

TEAM_NAMES = {
    "ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills",
    "CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns",
    "DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers",
    "HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs",
    "LV":"Las Vegas Raiders","LAC":"Los Angeles Chargers","LAR":"Los Angeles Rams","MIA":"Miami Dolphins",
    "MIN":"Minnesota Vikings","NE":"New England Patriots","NO":"New Orleans Saints","NYG":"New York Giants",
    "NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SF":"San Francisco 49ers",
    "SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders",
}
_PLAYER_STATS_COLUMNS = {
    "season", "week", "season_type", "game_id", "game_date", "player_id", "gsis_id",
    "player_name", "player_display_name", "position", "team", "opponent_team", "targets",
    "receptions", "receiving_yards", "receiving_tds",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _canonical_game_id(source_id: Any) -> str:
    return f"kyre:nfl:game:{_text(source_id)}"


def _canonical_team_id(team: Any) -> str:
    return f"kyre:nfl:team:{canonical_team_abbr(team)}"


def _canonical_player_id(source_id: Any) -> str:
    return f"kyre:nfl:player:{_text(source_id)}"


def _team_logo(team: Any) -> str:
    return f"{NFL_OFFICIAL_LOGO_BASE}/{canonical_team_abbr(team)}.svg"


def _parse_kickoff(row: Mapping[str, Any]) -> datetime | None:
    day = _text(row.get("gameday"))[:10]
    clock = _text(row.get("gametime"))
    if not day or not clock:
        return None
    try:
        return datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=ET)
    except ValueError:
        return None


def select_upcoming_week(frame: pd.DataFrame, *, now_et: datetime | None = None) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    now = now_et or datetime.now(ET)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=ET)
    else:
        now = now.astimezone(ET)
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for _, raw in frame.iterrows():
        if _text(raw.get("game_type")).upper() != "REG":
            continue
        kickoff = _parse_kickoff(raw)
        if kickoff is None or kickoff <= now:
            continue
        try:
            season = int(raw.get("season"))
            week = int(raw.get("week"))
        except (TypeError, ValueError):
            continue
        away = canonical_team_abbr(raw.get("away_team"))
        home = canonical_team_abbr(raw.get("home_team"))
        source_game_id = _text(raw.get("game_id"))
        if not source_game_id or not away or not home:
            continue
        candidates.append((kickoff, {
            "source_game_id": source_game_id,
            "canonical_game_id": _canonical_game_id(source_game_id),
            "season": season,
            "week": week,
            "game_date": kickoff.date().isoformat(),
            "kickoff_et": kickoff.isoformat(),
            "away": away,
            "home": home,
            "away_name": TEAM_NAMES.get(away, away),
            "home_name": TEAM_NAMES.get(home, home),
            "away_canonical_team_id": _canonical_team_id(away),
            "home_canonical_team_id": _canonical_team_id(home),
            "away_logo_url": _team_logo(away),
            "home_logo_url": _team_logo(home),
        }))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0])
    first = candidates[0][1]
    selected = [
        row for _kickoff, row in candidates
        if row["season"] == first["season"] and row["week"] == first["week"]
    ]
    selected.sort(key=lambda row: row["kickoff_et"])
    return selected


@lru_cache(maxsize=8)
def _load_player_stats(season: int) -> pd.DataFrame:
    response = requests.get(PLAYER_STATS_URL.format(season=int(season)), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return pd.read_csv(
        BytesIO(response.content),
        usecols=lambda name: name in _PLAYER_STATS_COLUMNS,
        low_memory=False,
    )


@lru_cache(maxsize=4)
def _load_weekly_roster(season: int) -> pd.DataFrame:
    response = requests.get(WEEKLY_ROSTER_URL.format(season=int(season)), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content), low_memory=False)


def _completed_receiving_rows(frame: pd.DataFrame, cutoff_day: str) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    rows = frame.copy()
    if "season_type" in rows.columns:
        rows = rows[rows["season_type"].astype(str).str.upper().eq("REG")]
    if "game_date" in rows.columns:
        rows = rows[rows["game_date"].astype(str).str[:10] < str(cutoff_day)[:10]]
    out: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        source_id = _text(row.get("gsis_id") or row.get("player_id"))
        team = canonical_team_abbr(row.get("team"))
        opponent = canonical_team_abbr(row.get("opponent_team"))
        receptions = _number(row.get("receptions"))
        yards = _number(row.get("receiving_yards"))
        targets = _number(row.get("targets"))
        tds = _number(row.get("receiving_tds"))
        if not source_id or not team or not opponent or receptions is None or yards is None:
            continue
        out.append({
            "source_game_id": _text(row.get("game_id")),
            "game_date": _text(row.get("game_date"))[:10],
            "week": int(_number(row.get("week")) or 0),
            "team_abbr": team,
            "opponent_abbr": opponent,
            "player_source_id": source_id,
            "player_name": _text(row.get("player_display_name") or row.get("player_name")),
            "position": _text(row.get("position")).upper(),
            "targets": float(targets or 0.0),
            "receptions": float(receptions),
            "receiving_yards": float(yards),
            "receiving_touchdowns": float(tds or 0.0),
        })
    out.sort(key=lambda item: (item["game_date"], item["source_game_id"], item["player_source_id"]))
    return out


def _resolve_roster_week(frame: pd.DataFrame, season: int, requested_week: int) -> int | None:
    if frame.empty or not {"season", "week"}.issubset(frame.columns):
        return None
    seasons = pd.to_numeric(frame["season"], errors="coerce")
    weeks = pd.to_numeric(frame["week"], errors="coerce")
    published = sorted({
        int(value) for value in weeks[seasons.eq(int(season))].dropna().tolist()
        if int(value) <= int(requested_week)
    })
    if not published:
        return None
    resolved = published[-1]
    return resolved if int(requested_week) - resolved <= 1 else None


def _roster_rows(frame: pd.DataFrame, *, season: int, week: int) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    required = {"season", "week", "team", "position", "status", "full_name", "gsis_id"}
    if not required.issubset(frame.columns):
        return []
    resolved = _resolve_roster_week(frame, season, week)
    if resolved is None:
        return []
    work = frame.copy()
    work["season_num"] = pd.to_numeric(work["season"], errors="coerce")
    work["week_num"] = pd.to_numeric(work["week"], errors="coerce")
    selected = work[(work["season_num"] == int(season)) & (work["week_num"] == int(resolved))]
    out: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        source_id = _text(row.get("gsis_id"))
        team = canonical_team_abbr(row.get("team"))
        position = _text(row.get("position")).upper()
        status = _text(row.get("status")).upper()
        name = _text(row.get("full_name"))
        if not source_id or not team or not name or position not in RECEIVING_POSITIONS:
            continue
        out.append({
            "player_source_id": source_id,
            "canonical_player_id": _canonical_player_id(source_id),
            "canonical_team_id": _canonical_team_id(team),
            "player_name": name,
            "team_abbr": team,
            "position": position,
            "active": status in ACTIVE_STATUSES,
            "status": status,
            "headshot_url": _text(row.get("headshot_url")),
            "jersey_number": _text(row.get("jersey_number")),
            "roster_week": resolved,
        })
    return out


def _profile(player: Mapping[str, Any], game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_id = _text(player.get("player_source_id"))
    rows = [dict(row) for row in game_rows if _text(row.get("player_source_id")) == source_id]
    rows.sort(key=lambda item: (item.get("game_date") or "", item.get("source_game_id") or ""))
    receptions = sum(float(row.get("receptions") or 0.0) for row in rows)
    yards = sum(float(row.get("receiving_yards") or 0.0) for row in rows)
    targets = sum(float(row.get("targets") or 0.0) for row in rows)
    touchdowns = sum(float(row.get("receiving_touchdowns") or 0.0) for row in rows)
    games = len(rows)
    recent = list(reversed(rows[-5:]))
    return {
        "sample_games": games,
        "targets": targets if games else None,
        "receptions": receptions if games else None,
        "receiving_yards": yards if games else None,
        "receiving_touchdowns": touchdowns if games else None,
        "targets_per_game": targets / games if games else None,
        "receptions_per_game": receptions / games if games else None,
        "receiving_yards_per_game": yards / games if games else None,
        "yards_per_reception": yards / receptions if receptions > 0 else None,
        "recent_games": recent,
        "recent5_yards_avg": (
            sum(float(row.get("receiving_yards") or 0.0) for row in recent) / len(recent)
            if recent else None
        ),
    }


def _defense_profile(team: str, game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    wanted = canonical_team_abbr(team)
    rows = [row for row in game_rows if canonical_team_abbr(row.get("opponent_abbr")) == wanted]
    game_ids = {row.get("source_game_id") for row in rows if row.get("source_game_id")}
    games = len(game_ids)
    receptions = sum(float(row.get("receptions") or 0.0) for row in rows)
    yards = sum(float(row.get("receiving_yards") or 0.0) for row in rows)
    touchdowns = sum(float(row.get("receiving_touchdowns") or 0.0) for row in rows)
    return {
        "data_available": games > 0 and receptions > 0,
        "canonical_team_id": _canonical_team_id(wanted),
        "team_abbr": wanted,
        "sample_games": games,
        "receptions_allowed_per_game": receptions / games if games else None,
        "receiving_yards_allowed_per_game": yards / games if games else None,
        "yards_per_reception_allowed": yards / receptions if receptions > 0 else None,
        "receiving_touchdowns_allowed_per_game": touchdowns / games if games else None,
    }


def _history(player_source_id: str, opponent: str, game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    wanted_opp = canonical_team_abbr(opponent)
    rows = [
        dict(row) for row in game_rows
        if _text(row.get("player_source_id")) == _text(player_source_id)
        and canonical_team_abbr(row.get("opponent_abbr")) == wanted_opp
    ]
    rows.sort(key=lambda item: (item.get("game_date") or "", item.get("source_game_id") or ""))
    recent = list(reversed(rows[-5:]))
    return {
        "available": bool(recent),
        "games": len(recent),
        "avg_receiving_yards": (
            sum(float(row.get("receiving_yards") or 0.0) for row in recent) / len(recent)
            if recent else None
        ),
        "games_detail": recent,
    }


def _market_index(
    game: Mapping[str, Any],
    roster_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    try:
        observations = direct_book.collect_fanduel_game_markets(game, timeout=4)
    except Exception as exc:
        return {}, {
            "state": "DATA_UNAVAILABLE",
            "reason": f"direct market read failed: {type(exc).__name__}",
            "verified_absence": False,
        }
    if not observations:
        return {}, {
            "state": "VERIFIED_NO_STANDARD_MARKET",
            "reason": "no open standard two-way Receiving Yards observation returned",
            "verified_absence": True,
        }
    mapped: dict[str, dict[str, Any]] = {}
    ambiguous = 0
    for observation in observations:
        roster = direct_book.reconcile_observation_to_roster(observation, roster_rows)
        if roster is None:
            ambiguous += 1
            continue
        canonical_id = _text(roster.get("canonical_player_id"))
        if not canonical_id or canonical_id in mapped:
            ambiguous += 1
            mapped.pop(canonical_id, None)
            continue
        mapped[canonical_id] = {
            **dict(observation),
            "canonical_player_id": canonical_id,
            "canonical_team_id": _text(roster.get("canonical_team_id")),
            "identity_verified": True,
            "sportsbook_projection_influence": 0.0,
        }
    return mapped, {
        "state": "READY" if mapped else "PLAYER_MAPPING_UNAVAILABLE",
        "reason": "" if mapped else "market observations did not resolve to unique active roster identity",
        "verified_absence": False,
        "mapped_count": len(mapped),
        "ambiguous_count": ambiguous,
    }


def _team_bundle(
    *,
    team: str,
    opponent: str,
    game: Mapping[str, Any],
    roster_rows: list[dict[str, Any]],
    game_rows: list[dict[str, Any]],
    markets: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    team = canonical_team_abbr(team)
    opponent = canonical_team_abbr(opponent)
    defense = _defense_profile(opponent, game_rows)
    candidates: list[dict[str, Any]] = []
    for roster in roster_rows:
        if canonical_team_abbr(roster.get("team_abbr")) != team or roster.get("active") is not True:
            continue
        profile = _profile(roster, game_rows)
        market = dict(markets.get(_text(roster.get("canonical_player_id"))) or {})
        meaningful = int(profile.get("sample_games") or 0) > 0 or bool(market)
        if not meaningful:
            continue
        player = {**dict(roster), **profile}
        player["matchup_history"] = _history(_text(roster.get("player_source_id")), opponent, game_rows)
        player["market"] = market if market else {
            "state": "NO_VERIFIED_PLAYER_MARKET",
            "sportsbook_projection_influence": 0.0,
        }
        player["projection"] = projection_model.build_player_projection(
            canonical_game_id=_text(game.get("canonical_game_id")),
            player=player,
            opponent_pass_defense=defense,
        )
        candidates.append(player)
    candidates.sort(key=lambda row: (
        0 if (row.get("market") or {}).get("identity_verified") is True else 1,
        -float(row.get("targets") or 0.0),
        -float(row.get("receiving_yards") or 0.0),
        _text(row.get("player_name")),
    ))
    selected = candidates[:MAX_RECEIVERS_PER_TEAM]
    return {
        "canonical_team_id": _canonical_team_id(team),
        "team_abbr": team,
        "team_name": TEAM_NAMES.get(team, team),
        "team_logo_url": _team_logo(team),
        "opponent_canonical_team_id": _canonical_team_id(opponent),
        "opponent_abbr": opponent,
        "opponent_pass_defense": defense,
        "players": selected,
        "player_count": len(selected),
    }


def build_slate_bundle(*, target_date: str | None = None, now_et: datetime | None = None) -> dict[str, Any]:
    captured = datetime.now(timezone.utc).isoformat()
    try:
        games = select_upcoming_week(_load_games_csv(), now_et=now_et)
    except Exception as exc:
        return {
            "ready": False,
            "reason": f"schedule unavailable: {type(exc).__name__}",
            "schema_version": SCHEMA_VERSION,
            "service": SERVICE,
            "gateway": GATEWAY,
            "games": [],
            "game_count": 0,
        }
    if target_date:
        games = [row for row in games if row.get("game_date") == str(target_date)[:10]]
    if not games:
        return {
            "ready": True,
            "reason": "",
            "schema_version": SCHEMA_VERSION,
            "service": SERVICE,
            "gateway": GATEWAY,
            "captured_at_utc": captured,
            "games": [],
            "game_count": 0,
            "semantic_state": "NO_UPCOMING_GAMES",
            "sportsbook_projection_influence": 0.0,
        }

    season = int(games[0]["season"])
    week = int(games[0]["week"])
    cutoff_day = min(str(row["game_date"]) for row in games)
    try:
        stats_frame = _load_player_stats(season)
        prior_frame = _load_player_stats(season - 1)
        roster_frame = _load_weekly_roster(season)
        game_rows = _completed_receiving_rows(stats_frame, cutoff_day)
        prior_rows = _completed_receiving_rows(prior_frame, cutoff_day)
        history_rows = prior_rows + game_rows
        roster_rows = _roster_rows(roster_frame, season=season, week=week)
    except Exception as exc:
        return {
            "ready": False,
            "reason": f"verified receiving inputs unavailable: {type(exc).__name__}",
            "schema_version": SCHEMA_VERSION,
            "service": SERVICE,
            "gateway": GATEWAY,
            "games": [],
            "game_count": 0,
        }

    bundles: list[dict[str, Any]] = []
    for game in games:
        markets, market_state = _market_index(game, roster_rows)
        away = _team_bundle(
            team=_text(game.get("away")), opponent=_text(game.get("home")), game=game,
            roster_rows=roster_rows, game_rows=history_rows, markets=markets,
        )
        home = _team_bundle(
            team=_text(game.get("home")), opponent=_text(game.get("away")), game=game,
            roster_rows=roster_rows, game_rows=history_rows, markets=markets,
        )
        bundles.append({**dict(game), "teams": [away, home], "market_state": market_state})

    return {
        "ready": True,
        "reason": "",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "service": SERVICE,
        "gateway": GATEWAY,
        "captured_at_utc": captured,
        "season": season,
        "week": week,
        "games": bundles,
        "game_count": len(bundles),
        "sportsbook_projection_influence": 0.0,
        "routing": {
            "application_gateway": "KYRE_SPORTS_API",
            "schedule": "nflverse games",
            "roster_identity": "nflverse weekly roster GSIS",
            "receiving_stats_history": "nflverse weekly player summaries",
            "team_assets": "NFL official CDN",
            "market": "FanDuel direct display-only",
            "player_market_identity": "exact team + jersey + position",
            "player_name_matching": False,
            "fuzzy_matching": False,
            "missing_to_zero": False,
            "semantic_empty_states": True,
            "sportsbook_line_averaging": False,
            "sportsbook_projection_influence": 0.0,
        },
    }


@router.get("")
def slate(date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict[str, Any]:
    return build_slate_bundle(target_date=date)


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "ready": True,
        "schema_version": SCHEMA_VERSION,
        "service": SERVICE,
        "gateway": GATEWAY,
        "model_version": MODEL_VERSION,
        "sportsbook_projection_influence": 0.0,
        "upcoming_only": True,
        "semantic_empty_states": True,
    }


__all__ = [
    "GATEWAY", "MODEL_VERSION", "SCHEMA_VERSION", "SERVICE",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "build_slate_bundle", "router",
    "select_upcoming_week", "slate", "status",
]
