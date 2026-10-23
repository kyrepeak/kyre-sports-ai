"""Kyre Sports API league-wide NFL Rushing Yards RB1/RB2 slate.

The application receives one canonical response. This route owns schedule
eligibility, verified running-back identity, workload-derived RB1/RB2 roles,
market-blind projection inputs, direct-book observations, semantic empty states,
provenance, and the Page 2 detail payload.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
import math
import re
from statistics import NormalDist, pstdev
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from fastapi import APIRouter, Query

import nfl_rushing_yards_projection_v2 as projection_model
from sports_api.collectors import nfl_fanduel_rushing_yards_nflverse_v1 as direct_book
from sports_api.nfl_data_nflverse_v1 import _load_games_csv, canonical_team_abbr

router = APIRouter(prefix="/api/v1/nfl/rushing-yards/slate", tags=["nfl-rushing-yards-slate"])
SCHEMA_VERSION = "nfl_rushing_yards_simple_rb_grid_v1"
SERVICE = "kyre-sports-api"
GATEWAY = "Kyre Sports API"
ET = ZoneInfo("America/New_York")
REQUEST_TIMEOUT = 12
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
WEEKLY_ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.csv"
NFL_OFFICIAL_LOGO_BASE = "https://static.www.nfl.com/t_q-best/league/api/clubs/logos"
ACTIVE_STATUSES = frozenset({"ACT", "ACTIVE"})

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
PBP_COLUMNS = (
    "game_id","season","season_type","week","game_date","posteam","defteam","no_play",
    "rusher_player_id","rusher_player_name","rush_attempt","rushing_yards","rush_touchdown",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _canonical_player_id(source_id: Any) -> str | None:
    raw = _text(source_id)
    return f"kyre:nfl:player:{raw}" if raw else None


def _canonical_team_id(team: Any) -> str:
    return f"kyre:nfl:team:{canonical_team_abbr(team)}"


def _canonical_game_id(source_id: Any) -> str | None:
    raw = _text(source_id)
    return f"kyre:nfl:game:{raw}" if raw else None


def _team_logo(team: str) -> str:
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
    """Return only not-yet-started games from the next active regular-season week.

    Once kickoff passes, that game is removed. When the final game in a week has
    started, the next future week automatically becomes authoritative.
    """
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
        if not away or not home or not source_game_id:
            continue
        candidates.append((kickoff, {
            "source_game_id": source_game_id,
            "game_id": _canonical_game_id(source_game_id),
            "season": season,
            "week": week,
            "game_date": kickoff.date().isoformat(),
            "kickoff_et": kickoff.isoformat(),
            "away": away,
            "home": home,
            "away_name": TEAM_NAMES.get(away, away),
            "home_name": TEAM_NAMES.get(home, home),
            "away_team_id": _canonical_team_id(away),
            "home_team_id": _canonical_team_id(home),
        }))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0])
    first = candidates[0][1]
    selected = [row for kickoff, row in candidates if row["season"] == first["season"] and row["week"] == first["week"]]
    selected.sort(key=lambda row: row["kickoff_et"])
    return selected


@lru_cache(maxsize=4)
def _load_pbp(season: int) -> pd.DataFrame:
    response = requests.get(PBP_URL.format(season=int(season)), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(
        BytesIO(response.content), compression="gzip",
        usecols=lambda name: name in PBP_COLUMNS, low_memory=False,
    )


@lru_cache(maxsize=4)
def _load_weekly_roster(season: int) -> pd.DataFrame:
    response = requests.get(WEEKLY_ROSTER_URL.format(season=int(season)), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content), low_memory=False)


def _completed_rush_rows(frame: pd.DataFrame, cutoff_day: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    needed = {"game_id", "posteam", "defteam", "rusher_player_id", "rush_attempt", "rushing_yards"}
    if not needed.issubset(frame.columns):
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


def _player_game_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped = frame.dropna(subset=["game_id", "posteam", "defteam", "rusher_player_id"]).groupby(
        ["game_id", "posteam", "defteam", "rusher_player_id", "rusher_player_name"], dropna=True
    )
    out: list[dict[str, Any]] = []
    for (game_id, team, opponent, source_id, name), group in grouped:
        attempts = int(pd.to_numeric(group["rush_attempt"], errors="coerce").eq(1.0).sum())
        yards_series = pd.to_numeric(group["rushing_yards"], errors="coerce")
        yards = float(yards_series.sum(min_count=1)) if yards_series.notna().any() else None
        if attempts <= 0 or yards is None:
            continue
        game_date = _text(group["game_date"].iloc[0])[:10] if "game_date" in group.columns else ""
        week = int(_num(group["week"].iloc[0]) or 0) if "week" in group.columns else 0
        touchdowns = int(pd.to_numeric(group.get("rush_touchdown", pd.Series(dtype=float)), errors="coerce").eq(1.0).sum())
        out.append({
            "source_game_id": _text(game_id),
            "game_date": game_date,
            "week": week,
            "team_abbr": canonical_team_abbr(team),
            "opponent_abbr": canonical_team_abbr(opponent),
            "player_source_id": _text(source_id),
            "player_name": _text(name),
            "attempts": attempts,
            "rushing_yards": yards,
            "rushing_touchdowns": touchdowns,
        })
    out.sort(key=lambda row: (row.get("game_date") or "", row.get("source_game_id") or ""))
    return out


def _resolve_roster_week(frame: pd.DataFrame, season: int, requested_week: int) -> int | None:
    if frame.empty or not {"season", "week"}.issubset(frame.columns):
        return None
    seasons = pd.to_numeric(frame["season"], errors="coerce")
    weeks = pd.to_numeric(frame["week"], errors="coerce")
    published = sorted({int(value) for value in weeks[seasons.eq(int(season))].dropna().tolist() if int(value) <= int(requested_week)})
    if not published:
        return None
    resolved = published[-1]
    return resolved if requested_week - resolved <= 1 else None


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
    rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        source_id = _text(row.get("gsis_id"))
        team = canonical_team_abbr(row.get("team"))
        position = _text(row.get("position")).upper()
        status = _text(row.get("status")).upper()
        name = _text(row.get("full_name"))
        if not source_id or not team or not name:
            continue
        rows.append({
            "player_source_id": source_id,
            "player_name": name,
            "team_abbr": team,
            "position": position,
            "active": status in ACTIVE_STATUSES,
            "status": status,
            "headshot_url": _text(row.get("headshot_url")),
            "jersey_number": _text(row.get("jersey_number")),
            "roster_week": resolved,
            "roster_week_lag": int(week) - int(resolved),
        })
    return rows


def select_team_running_backs(team: str, roster_rows: list[dict[str, Any]], game_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive RB1/RB2 from active verified RB identity + verified rushing workload."""
    wanted = canonical_team_abbr(team)
    stats: dict[str, dict[str, float]] = {}
    for row in game_rows or []:
        if canonical_team_abbr(row.get("team_abbr")) != wanted:
            continue
        source_id = _text(row.get("player_source_id"))
        if not source_id:
            continue
        bucket = stats.setdefault(source_id, {"attempts": 0.0, "rushing_yards": 0.0, "games": 0.0})
        bucket["attempts"] += float(_num(row.get("attempts")) or 0.0)
        bucket["rushing_yards"] += float(_num(row.get("rushing_yards")) or 0.0)
        bucket["games"] += float(_num(row.get("games")) or 1.0)
    candidates: list[dict[str, Any]] = []
    for raw in roster_rows or []:
        if canonical_team_abbr(raw.get("team_abbr")) != wanted or _text(raw.get("position")).upper() != "RB" or raw.get("active") is not True:
            continue
        source_id = _text(raw.get("player_source_id"))
        if not source_id:
            continue
        stat = stats.get(source_id, {"attempts": 0.0, "rushing_yards": 0.0, "games": 0.0})
        candidates.append({**raw, "verified_attempts": stat["attempts"], "verified_rushing_yards": stat["rushing_yards"], "verified_games": stat["games"]})
    candidates.sort(key=lambda row: (-float(row["verified_attempts"]), -float(row["verified_rushing_yards"]), _text(row.get("player_name"))))
    selected = candidates[:2]
    for index, row in enumerate(selected):
        row["role"] = "RB1" if index == 0 else "RB2"
        row["role_source"] = "VERIFIED_WORKLOAD_DERIVATION"
    return selected


def _profile(player: Mapping[str, Any], game_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_id = _text(player.get("player_source_id"))
    rows = [dict(row) for row in game_rows if _text(row.get("player_source_id")) == source_id]
    rows.sort(key=lambda row: (row.get("game_date") or "", row.get("source_game_id") or ""))
    attempts = sum(float(_num(row.get("attempts")) or 0.0) for row in rows)
    yards = sum(float(_num(row.get("rushing_yards")) or 0.0) for row in rows)
    games = len(rows)
    recent = list(reversed(rows[-5:]))
    return {
        "sample_games": games,
        "carries": attempts if games else None,
        "rushing_yards": yards if games else None,
        "carries_per_game": (attempts / games) if games else None,
        "rushing_yards_per_game": (yards / games) if games else None,
        "yards_per_carry": (yards / attempts) if attempts > 0 else None,
        "rushing_touchdowns": sum(int(row.get("rushing_touchdowns") or 0) for row in rows) if games else None,
        "last5_average": (sum(float(row["rushing_yards"]) for row in recent) / len(recent)) if recent else None,
        "recent_games": recent,
    }


def _defense_profiles(game_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_defense_game: dict[tuple[str, str], dict[str, float]] = {}
    for row in game_rows:
        defense = canonical_team_abbr(row.get("opponent_abbr"))
        game_id = _text(row.get("source_game_id"))
        if not defense or not game_id:
            continue
        bucket = by_defense_game.setdefault((defense, game_id), {"attempts": 0.0, "yards": 0.0, "touchdowns": 0.0})
        bucket["attempts"] += float(_num(row.get("attempts")) or 0.0)
        bucket["yards"] += float(_num(row.get("rushing_yards")) or 0.0)
        bucket["touchdowns"] += float(_num(row.get("rushing_touchdowns")) or 0.0)
    grouped: dict[str, list[dict[str, float]]] = {}
    for (team, _game_id), values in by_defense_game.items():
        grouped.setdefault(team, []).append(values)
    out: dict[str, dict[str, Any]] = {}
    for team, games in grouped.items():
        attempts = sum(game["attempts"] for game in games)
        yards = sum(game["yards"] for game in games)
        n = len(games)
        out[team] = {
            "team_id": _canonical_team_id(team),
            "team_abbr": team,
            "games": n,
            "rush_attempts_allowed_per_game": attempts / n if n else None,
            "rush_yards_allowed_per_game": yards / n if n else None,
            "yards_per_carry_allowed": yards / attempts if attempts > 0 else None,
            "rushing_touchdowns_allowed_per_game": sum(game["touchdowns"] for game in games) / n if n else None,
        }
    ranking = sorted(((team, row["rush_yards_allowed_per_game"]) for team, row in out.items() if row.get("rush_yards_allowed_per_game") is not None), key=lambda item: float(item[1]))
    ranks = {team: index + 1 for index, (team, _value) in enumerate(ranking)}
    for team, row in out.items():
        rank = ranks.get(team)
        row["rank"] = rank
        row["grade"] = "TOUGH" if rank and rank <= 8 else "FAVORABLE" if rank and rank >= 21 else "MEDIUM" if rank else "CHECK"
    return out


def _history_for_player(player_source_id: str, opponent: str, history_rows: list[dict[str, Any]], *, history_complete: bool) -> dict[str, Any]:
    matched = [row for row in history_rows if _text(row.get("player_source_id")) == player_source_id and canonical_team_abbr(row.get("opponent_abbr")) == canonical_team_abbr(opponent)]
    matched.sort(key=lambda row: row.get("game_date") or "")
    if not matched:
        if history_complete:
            return {"status": "FIRST_CAREER_MATCHUP", "display": "First career matchup", "games": 0, "games_detail": []}
        return {"status": "DATA_UNAVAILABLE", "display": "Historical verification pending", "games": 0, "games_detail": []}
    return {
        "status": "VERIFIED",
        "display": f"{len(matched)} verified prior meeting{'s' if len(matched) != 1 else ''}",
        "games": len(matched),
        "average_rushing_yards": sum(float(row["rushing_yards"]) for row in matched) / len(matched),
        "average_attempts": sum(float(row["attempts"]) for row in matched) / len(matched),
        "games_detail": list(reversed(matched[-5:])),
    }


def market_state(observation: Mapping[str, Any] | None) -> dict[str, Any]:
    if not observation:
        return {
            "status": "MARKET_NOT_POSTED",
            "sportsbook": None,
            "market": "Rushing Yards",
            "line": None,
            "over_odds": None,
            "under_odds": None,
            "timestamp": None,
        }
    return {
        "status": "VERIFIED",
        "sportsbook": _text(observation.get("sportsbook")) or None,
        "market": "Rushing Yards",
        "line": _num(observation.get("line")),
        "over_odds": int(_num(observation.get("over_odds"))) if _num(observation.get("over_odds")) is not None else None,
        "under_odds": int(_num(observation.get("under_odds"))) if _num(observation.get("under_odds")) is not None else None,
        "timestamp": _text(observation.get("source_timestamp")) or None,
        "provider_market_id": _text(observation.get("provider_market_id")) or None,
        "provider_player_id": _text(observation.get("provider_player_id")) or None,
        "identity_resolution": "UNIQUE_TEAM_POSITION_NAME_RECONCILIATION",
    }


def _market_for_player(player: Mapping[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    team = canonical_team_abbr(player.get("team_abbr"))
    name = _norm(player.get("player_name"))
    matched = [row for row in observations if canonical_team_abbr(row.get("team_abbr")) == team and _norm(row.get("player_name")) == name and _text(row.get("position")).upper() in {"RB", "RUNNING BACK"}]
    if len(matched) != 1:
        return market_state(None)
    return market_state(matched[0])


def _probabilities(projection: float | None, line: float | None, recent: Iterable[Any]) -> tuple[float | None, float | None]:
    if projection is None or line is None:
        return None, None
    values = [float(value) for value in (_num(v) for v in recent) if value is not None]
    sigma = pstdev(values) if len(values) >= 2 else max(12.0, abs(projection) * 0.28)
    sigma = max(10.0, min(45.0, sigma))
    over = 1.0 - NormalDist(mu=projection, sigma=sigma).cdf(line)
    over = max(0.01, min(0.99, over))
    return over, 1.0 - over


def _decision(edge: float | None, over: float | None, under: float | None) -> tuple[str, str]:
    if edge is None or over is None or under is None:
        return "CHECK", "MARKET PENDING"
    side = "OVER" if edge >= 0 else "UNDER"
    probability = over if side == "OVER" else under
    magnitude = abs(edge)
    if magnitude >= 10 and probability >= 0.62:
        return side, "HIGH"
    if magnitude >= 5 and probability >= 0.57:
        return side, "MEDIUM"
    return side, "LEAN"


def _why(profile: Mapping[str, Any], defense: Mapping[str, Any], projection: Mapping[str, Any], market: Mapping[str, Any]) -> list[str]:
    bullets: list[str] = []
    carries = _num(profile.get("carries_per_game"))
    if carries is not None:
        bullets.append(f"Verified workload baseline: {carries:.1f} carries per game.")
    grade = _text(defense.get("grade"))
    allowed = _num(defense.get("rush_yards_allowed_per_game"))
    if grade and allowed is not None:
        bullets.append(f"Opponent run-defense grade is {grade} at {allowed:.1f} rushing yards allowed per game.")
    if projection.get("ready") is True:
        bullets.append(f"Market-blind rushing projection: {float(projection['projection_yards']):.1f} yards.")
    line = _num(market.get("line"))
    if line is None:
        bullets.append("No verified current rushing-yard market is posted yet; no line was fabricated.")
    return bullets


def _collect_markets(games: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {str(game["source_game_id"]): [] for game in games}
    if not games:
        return results
    with ThreadPoolExecutor(max_workers=min(4, len(games))) as pool:
        futures = {pool.submit(direct_book.collect_fanduel_game_markets, game): str(game["source_game_id"]) for game in games}
        for future in as_completed(futures):
            game_id = futures[future]
            try:
                results[game_id] = list(future.result() or [])
            except Exception:
                results[game_id] = []
    return results


def _history_rows(season: int, cutoff_day: str, current_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    rows = list(current_rows)
    complete = True
    for prior in range(int(season) - 2, int(season)):
        try:
            frame = _completed_rush_rows(_load_pbp(prior), "9999-12-31")
            rows.extend(_player_game_rows(frame))
        except Exception:
            complete = False
    return rows, complete


def build_slate_bundle(*, target_date: str | None = None, now_et: datetime | None = None) -> dict[str, Any]:
    fetched_at = _utc_now()
    try:
        games_frame = _load_games_csv()
        games = select_upcoming_week(games_frame, now_et=now_et)
    except Exception as exc:
        return {"ready": False, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": f"Schedule provider degraded: {type(exc).__name__}", "running_backs": [], "running_back_count": 0, "fetched_at": fetched_at}
    if target_date:
        games = [game for game in games if game.get("game_date") == str(target_date)[:10]]
    if not games:
        return {"ready": True, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": "NO_UPCOMING_GAMES", "running_backs": [], "running_back_count": 0, "games": [], "fetched_at": fetched_at, "routing": _routing_contract()}

    season = int(games[0]["season"])
    week = int(games[0]["week"])
    cutoff_day = min(game["game_date"] for game in games)
    try:
        current_frame = _completed_rush_rows(_load_pbp(season), cutoff_day)
        current_game_rows = _player_game_rows(current_frame)
    except Exception as exc:
        return {"ready": False, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": f"Verified rushing statistics degraded: {type(exc).__name__}", "running_backs": [], "running_back_count": 0, "fetched_at": fetched_at}
    try:
        roster_rows = _roster_rows(_load_weekly_roster(season), season=season, week=week)
    except Exception as exc:
        return {"ready": False, "schema_version": SCHEMA_VERSION, "service": SERVICE, "gateway": GATEWAY, "reason": f"Verified roster provider degraded: {type(exc).__name__}", "running_backs": [], "running_back_count": 0, "fetched_at": fetched_at}

    defenses = _defense_profiles(current_game_rows)
    history_rows, history_complete = _history_rows(season, cutoff_day, current_game_rows)
    markets_by_game = _collect_markets(games)
    cards: list[dict[str, Any]] = []

    for game in games:
        for team, opponent, home_away in ((game["away"], game["home"], "AWAY"), (game["home"], game["away"], "HOME")):
            selected = select_team_running_backs(team, roster_rows, current_game_rows)
            defense = defenses.get(opponent) or {
                "team_id": _canonical_team_id(opponent), "team_abbr": opponent, "games": 0,
                "rush_attempts_allowed_per_game": None, "rush_yards_allowed_per_game": None,
                "yards_per_carry_allowed": None, "rushing_touchdowns_allowed_per_game": None,
                "rank": None, "grade": "CHECK",
            }
            for player in selected:
                profile = _profile(player, current_game_rows)
                projection = projection_model.build_projection(player=profile, opponent=defense)
                market = _market_for_player(player, markets_by_game.get(str(game["source_game_id"]), []))
                projection_yards = _num(projection.get("projection_yards")) if projection.get("ready") else None
                line = _num(market.get("line"))
                edge = (projection_yards - line) if projection_yards is not None and line is not None else None
                recent_yards = [row.get("rushing_yards") for row in profile.get("recent_games") or []]
                over, under = _probabilities(projection_yards, line, recent_yards)
                side, confidence = _decision(edge, over, under)
                history = _history_for_player(_text(player.get("player_source_id")), opponent, history_rows, history_complete=history_complete)
                player_id = _canonical_player_id(player.get("player_source_id"))
                detail = {
                    "player_id": player_id,
                    "player_name": player.get("player_name"),
                    "role": player.get("role"),
                    "role_source": player.get("role_source"),
                    "team_abbr": team,
                    "team_name": TEAM_NAMES.get(team, team),
                    "opponent_abbr": opponent,
                    "opponent_name": TEAM_NAMES.get(opponent, opponent),
                    "home_away": home_away,
                    "profile": profile,
                    "projection": projection,
                    "opponent_run_defense": defense,
                    "matchup_history": history,
                    "market": market,
                    "availability": {"status": "DATA_UNAVAILABLE", "display": "Availability data pending verification"},
                    "environment": {"status": "PREGAME", "display": "Pregame", "kickoff_et": game["kickoff_et"]},
                    "why_kyre_leans": _why(profile, defense, projection, market),
                    "source_lineage": {
                        "identity": "nflverse weekly roster",
                        "workload": "nflverse play-by-play",
                        "opponent_run_defense": "nflverse play-by-play derived",
                        "history": "nflverse play-by-play historical",
                        "market": market.get("sportsbook") or "semantic market state",
                        "projection": projection_model.MODEL_VERSION,
                    },
                }
                cards.append({
                    "player_id": player_id,
                    "player_source_id": player.get("player_source_id"),
                    "player_name": player.get("player_name"),
                    "position": "RB",
                    "role": player.get("role"),
                    "role_source": player.get("role_source"),
                    "headshot_url": player.get("headshot_url"),
                    "team_abbr": team,
                    "team_name": TEAM_NAMES.get(team, team),
                    "team_id": _canonical_team_id(team),
                    "team_logo_url": _team_logo(team),
                    "opponent_abbr": opponent,
                    "opponent_name": TEAM_NAMES.get(opponent, opponent),
                    "opponent_id": _canonical_team_id(opponent),
                    "opponent_logo_url": _team_logo(opponent),
                    "home_away": home_away,
                    "game_id": game["game_id"],
                    "source_game_id": game["source_game_id"],
                    "game_date": game["game_date"],
                    "game_time": game["kickoff_et"],
                    "season": season,
                    "week": week,
                    "market": market,
                    "projection_yards": projection_yards,
                    "edge_yards": edge,
                    "over_probability": over,
                    "under_probability": under,
                    "favored_side": side,
                    "confidence": confidence,
                    "last5_average": profile.get("last5_average"),
                    "carries_per_game": profile.get("carries_per_game"),
                    "yards_per_carry": profile.get("yards_per_carry"),
                    "opponent_rush_defense_grade": defense.get("grade"),
                    "data_status": "VERIFIED" if player_id else "BLOCKED_INVALID_IDENTITY",
                    "detail": detail,
                })
    cards.sort(key=lambda row: (row.get("game_time") or "", row.get("team_abbr") or "", 0 if row.get("role") == "RB1" else 1, row.get("player_name") or ""))
    return {
        "ready": True,
        "schema_version": SCHEMA_VERSION,
        "service": SERVICE,
        "gateway": GATEWAY,
        "reason": "",
        "season": season,
        "week": week,
        "slate_start": games[0]["game_date"],
        "slate_end": games[-1]["game_date"],
        "games": games,
        "game_count": len(games),
        "running_backs": cards,
        "running_back_count": len(cards),
        "fetched_at": fetched_at,
        "routing": _routing_contract(),
    }


def _routing_contract() -> dict[str, Any]:
    return {
        "application_gateway": GATEWAY,
        "field_first": True,
        "canonical_ids": True,
        "sportsbook_line_averaging": False,
        "missing_to_zero": False,
        "semantic_empty_states": True,
        "source_lineage": True,
        "upcoming_games_only": True,
        "kickoff_exclusive": True,
        "auto_roll_next_week": True,
        "market_source_policy": "direct sportsbook first available in this deployment; field-level fallback remains fail-closed",
        "statistics_source": "nflverse verified football data",
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "ready": True,
        "service": SERVICE,
        "gateway": GATEWAY,
        "schema_version": SCHEMA_VERSION,
        "page1": "simple all-RB1/RB2 board",
        "page2": "deep rushing analytics",
        "upcoming_games_only": True,
        "kickoff_exclusive": True,
        "auto_roll_next_week": True,
        "routing": _routing_contract(),
    }


@router.get("")
def slate(date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict[str, Any]:
    return build_slate_bundle(target_date=date)


__all__ = [
    "SCHEMA_VERSION", "SERVICE", "GATEWAY", "build_slate_bundle", "market_state",
    "select_team_running_backs", "select_upcoming_week", "router", "slate", "status",
]
