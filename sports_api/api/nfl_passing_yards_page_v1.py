"""Kyre Sports API NFL Passing Yards professional page bundle.

Application clients receive one normalized bundle from this route. Provider
selection, fallback, canonical identity, projection inputs, history, market
observations and provenance are owned here rather than in Streamlit.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from io import BytesIO
import math
import re
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import requests
from fastapi import APIRouter, Query

import nfl_passing_yards_context_v1 as context_model
import nfl_passing_yards_distribution_v1 as distribution_model
import nfl_passing_yards_market_v1 as market_model
import nfl_passing_yards_projection_v2 as projection_model
from sports_api.nfl_data_nflverse_v1 import canonical_team_abbr, _load_games_csv

router = APIRouter(prefix="/api/v1/nfl/passing-yards/page", tags=["nfl-passing-yards-page"])
SCHEMA_VERSION = "nfl_passing_yards_professional_v1"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
NFLVERSE_WEEKLY_ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.csv"
NFL_OFFICIAL_LOGO_BASE = "https://static.www.nfl.com/t_q-best/league/api/clubs/logos"
FANDUEL_BASE = "https://api.sportsbook.fanduel.com"
FANDUEL_KEY = "FhMFpcPWXMeyZxOx"
REQUEST_TIMEOUT = 14

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
NAME_TO_TEAM = {name: abbr for abbr, name in TEAM_NAMES.items()}
PBP_COLUMNS = (
    "game_id","season","season_type","week","game_date","posteam","defteam",
    "passer_player_id","passer_player_name","pass_attempt","complete_pass","passing_yards",
    "pass_touchdown","interception","sack","no_play",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _safe(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _canonical_player_id(value: Any) -> str | None:
    raw = _safe(value)
    return f"kyre:nfl:player:{raw}" if raw else None


def _canonical_team_id(abbr: str) -> str:
    return f"kyre:nfl:team:{canonical_team_abbr(abbr)}"


def _canonical_game_id(game_id: Any) -> str | None:
    raw = _safe(game_id)
    return f"kyre:nfl:game:{raw}" if raw else None


def pass_defense_grade(rank: Any) -> str:
    try:
        value = int(rank)
    except (TypeError, ValueError):
        return "CHECK"
    if not 1 <= value <= 32:
        return "CHECK"
    if value <= 8:
        return "TOUGH"
    if value <= 20:
        return "MEDIUM"
    return "FAVORABLE"


def _mean(values: Iterable[Any]) -> float | None:
    nums = [x for x in (_number(v) for v in values) if x is not None]
    return float(sum(nums) / len(nums)) if nums else None


def _sum(values: Iterable[Any]) -> float | None:
    nums = [x for x in (_number(v) for v in values) if x is not None]
    return float(sum(nums)) if nums else None


def summarize_qb_vs_opponent(rows: list[dict[str, Any]], *, qb_name: str, opponent: str) -> dict[str, Any]:
    wanted_name = _safe(qb_name).casefold()
    wanted_opp = canonical_team_abbr(opponent)
    matched = [
        row for row in rows
        if _safe(row.get("qb_name")).casefold() == wanted_name
        and canonical_team_abbr(row.get("opponent")) == wanted_opp
        and _number(row.get("passing_yards")) is not None
    ]
    if not matched:
        return {
            "available": False, "games": 0, "avg_passing_yards": None, "avg_attempts": None,
            "completion_pct": None, "avg_pass_tds": None, "avg_interceptions": None,
            "message": "No verified prior matchup history",
        }
    attempts = _sum(row.get("attempts") for row in matched)
    completions = _sum(row.get("completions") for row in matched)
    completion_pct = (100.0 * completions / attempts) if attempts and completions is not None else None
    return {
        "available": True,
        "games": len(matched),
        "avg_passing_yards": _mean(row.get("passing_yards") for row in matched),
        "avg_attempts": _mean(row.get("attempts") for row in matched),
        "completion_pct": completion_pct,
        "avg_pass_tds": _mean(row.get("pass_tds") for row in matched),
        "avg_interceptions": _mean(row.get("interceptions") for row in matched),
        "message": "Verified direct quarterback-versus-opponent history",
        "games_detail": matched[-5:],
    }


@lru_cache(maxsize=8)
def _load_pbp(season: int) -> pd.DataFrame:
    response = requests.get(PBP_URL.format(season=int(season)), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(
        BytesIO(response.content), compression="gzip",
        usecols=lambda name: name in PBP_COLUMNS, low_memory=False,
    )


def _completed_before(frame: pd.DataFrame, cutoff: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    rows = frame.copy()
    if "season_type" in rows:
        rows = rows[rows["season_type"].astype(str).str.upper().eq("REG")]
    if "game_date" in rows:
        rows = rows[rows["game_date"].astype(str).str[:10] < cutoff]
    if "no_play" in rows:
        rows = rows[~pd.to_numeric(rows["no_play"], errors="coerce").eq(1.0)]
    return rows


def _flag_sum(frame: pd.DataFrame, field: str) -> int | None:
    if field not in frame.columns or frame.empty:
        return None
    values = pd.to_numeric(frame[field], errors="coerce")
    if values.notna().sum() == 0:
        return None
    return int(values.eq(1.0).sum())


def _yards_sum(frame: pd.DataFrame) -> float | None:
    if "passing_yards" not in frame.columns or frame.empty:
        return None
    values = pd.to_numeric(frame["passing_yards"], errors="coerce")
    return float(values.sum(min_count=1)) if values.notna().any() else None


def _qb_game_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    needed = {"game_id","posteam","defteam","passer_player_name"}
    if frame.empty or not needed.issubset(frame.columns):
        return []
    out: list[dict[str, Any]] = []
    grouped = frame.dropna(subset=["game_id","passer_player_name"]).groupby(["game_id","posteam","defteam","passer_player_name"], dropna=True)
    for (game_id, team, opponent, name), group in grouped:
        attempts = _flag_sum(group, "pass_attempt")
        yards = _yards_sum(group)
        if attempts is None or attempts <= 0 or yards is None:
            continue
        ids = [str(v) for v in group.get("passer_player_id", pd.Series(dtype=object)).dropna().unique() if str(v).strip()]
        out.append({
            "game_id": str(game_id), "team": canonical_team_abbr(team), "opponent": canonical_team_abbr(opponent),
            "qb_name": str(name), "player_source_id": ids[0] if len(ids) == 1 else None,
            "attempts": attempts, "completions": _flag_sum(group,"complete_pass"), "passing_yards": yards,
            "pass_tds": _flag_sum(group,"pass_touchdown"), "interceptions": _flag_sum(group,"interception"),
        })
    return out


def _select_qb(team: str, game_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [row for row in game_rows if row.get("team") == team]
    if not rows:
        return None
    recent_ids = []
    for row in reversed(rows):
        identity = (row.get("player_source_id"), row.get("qb_name"))
        if identity not in recent_ids:
            recent_ids.append(identity)
    best = None
    best_key = None
    for player_id, name in recent_ids:
        samples = [r for r in rows if r.get("player_source_id") == player_id and r.get("qb_name") == name]
        key = (len(samples), sum(int(r.get("attempts") or 0) for r in samples))
        if best is None or key > best_key:
            best, best_key = {"player_source_id": player_id, "qb_name": name, "games": samples}, key
    return best


def _profile(qb: dict[str, Any]) -> dict[str, Any]:
    games = list(qb.get("games") or [])
    recent = games[-5:][::-1]
    recent3 = games[-3:]
    attempts = _sum(row.get("attempts") for row in games)
    completions = _sum(row.get("completions") for row in games)
    yards = _sum(row.get("passing_yards") for row in games)
    recent3_attempts = _sum(row.get("attempts") for row in recent3)
    recent3_yards = _sum(row.get("passing_yards") for row in recent3)
    count = len(games)
    return {
        "ready": bool(count and attempts and yards is not None),
        "player_id": _canonical_player_id(qb.get("player_source_id")),
        "qb_name": qb.get("qb_name"), "games": count,
        "passing_yards_per_game": (yards / count) if yards is not None and count else None,
        "attempts_per_game": (attempts / count) if attempts and count else None,
        "completion_pct": (100.0 * completions / attempts) if attempts and completions is not None else None,
        "yards_per_attempt": (yards / attempts) if attempts and yards is not None else None,
        "pass_tds": _sum(row.get("pass_tds") for row in games),
        "interceptions": _sum(row.get("interceptions") for row in games),
        "recent3_yards": recent3_yards,
        "recent3_attempts": recent3_attempts,
        "recent3_ypa": (recent3_yards / recent3_attempts) if recent3_attempts and recent3_yards is not None else None,
        "recent_games": recent,
    }


def _defense_profiles(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    rows = _qb_game_rows(frame)
    by_team: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_team.setdefault(str(row["opponent"]), []).append(row)
    raw: dict[str, dict[str, Any]] = {}
    for team, games in by_team.items():
        unique_games = sorted({str(r["game_id"]) for r in games})
        n = len(unique_games)
        yards = _sum(r.get("passing_yards") for r in games)
        attempts = _sum(r.get("attempts") for r in games)
        completions = _sum(r.get("completions") for r in games)
        recent_ids = unique_games[-3:]
        recent = [r for r in games if str(r.get("game_id")) in recent_ids]
        sacks_frame = frame[frame["defteam"].map(canonical_team_abbr).eq(team)] if "defteam" in frame.columns else pd.DataFrame()
        sacks = _flag_sum(sacks_frame, "sack")
        denom = (attempts or 0.0) + float(sacks or 0)
        raw[team] = {
            "games": n,
            "pass_yards_allowed_per_game": (yards / n) if yards is not None and n else None,
            "passing_attempts_allowed_per_game": (attempts / n) if attempts and n else None,
            "completion_pct_allowed": (100.0 * completions / attempts) if attempts and completions is not None else None,
            "yards_per_attempt_allowed": (yards / attempts) if attempts and yards is not None else None,
            "recent3_pass_yards_allowed": _mean(r.get("passing_yards") for r in recent),
            "recent3_ypa_allowed": (_sum(r.get("passing_yards") for r in recent) / _sum(r.get("attempts") for r in recent)) if _sum(r.get("attempts") for r in recent) else None,
            "sack_rate_generated": (100.0 * float(sacks) / denom) if sacks is not None and denom > 0 else None,
        }
    ranked = sorted(
        ((team, row["pass_yards_allowed_per_game"]) for team, row in raw.items() if row.get("pass_yards_allowed_per_game") is not None),
        key=lambda item: float(item[1]),
    )
    rank_by_team = {team: idx + 1 for idx, (team, _value) in enumerate(ranked)}
    for team, row in raw.items():
        rank = rank_by_team.get(team)
        row["rank"] = rank
        row["grade"] = pass_defense_grade(rank)
        row["team_id"] = _canonical_team_id(team)
        row["team_abbr"] = team
        row["team_name"] = TEAM_NAMES.get(team, team)
    return raw


def _team_pace(frame: pd.DataFrame, team: str) -> tuple[float | None, float | None]:
    if frame.empty or "posteam" not in frame.columns:
        return None, None
    rows = frame[frame["posteam"].map(canonical_team_abbr).eq(team)]
    if rows.empty or "game_id" not in rows.columns:
        return None, None
    games = int(rows["game_id"].dropna().astype(str).nunique())
    attempts = _flag_sum(rows, "pass_attempt")
    sacks = _flag_sum(rows, "sack")
    attempts_pg = (float(attempts) / games) if attempts is not None and games else None
    denom = float(attempts or 0) + float(sacks or 0)
    sack_rate = (100.0 * float(sacks) / denom) if sacks is not None and denom > 0 else None
    return attempts_pg, sack_rate


def _schedule_game(target_date: str | None) -> dict[str, Any] | None:
    frame = _load_games_csv()
    if frame.empty:
        return None
    rows = frame.copy()
    if "game_type" in rows.columns:
        rows = rows[rows["game_type"].astype(str).str.upper().eq("REG")]
    rows["_date"] = rows["gameday"].astype(str).str[:10]
    today = target_date or datetime.now(timezone.utc).date().isoformat()
    if target_date:
        rows = rows[rows["_date"].eq(target_date)]
    else:
        future = rows[rows["_date"] >= today]
        if future.empty:
            return None
        next_date = str(future["_date"].min())
        rows = future[future["_date"].eq(next_date)]
    if rows.empty:
        return None
    row = rows.sort_values(["_date", "gametime"] if "gametime" in rows.columns else ["_date"]).iloc[0]
    away = canonical_team_abbr(row.get("away_team"))
    home = canonical_team_abbr(row.get("home_team"))
    season = int(row.get("season"))
    week = int(row.get("week")) if _number(row.get("week")) is not None else None
    return {
        "game_id": _canonical_game_id(row.get("game_id")), "source_game_id": _safe(row.get("game_id")),
        "date": str(row.get("_date")), "season": season, "week": week,
        "away": away, "home": home, "away_team_id": _canonical_team_id(away), "home_team_id": _canonical_team_id(home),
        "away_name": TEAM_NAMES.get(away, away), "home_name": TEAM_NAMES.get(home, home),
        "away_logo_url": _official_team_logo_url(away), "home_logo_url": _official_team_logo_url(home),
        "kickoff": _safe(row.get("gametime")),
    }


def _fd_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    target = url + "?" + urlencode({k: str(v) for k, v in params.items()})
    req = Request(target, headers={
        "Accept":"application/json,text/plain,*/*","User-Agent":"Mozilla/5.0 (compatible; KyreSportsAPI-NFL/2.0; read-only)",
        "Origin":"https://sportsbook.fanduel.com","Referer":"https://sportsbook.fanduel.com/","x-sportsbook-region":"NJ",
    })
    with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        raw = response.read(20_000_000)
    import json
    payload = json.loads(raw.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [dict(item, _attachment_key=str(key)) for key, item in value.items() if isinstance(item, dict)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _market_name(row: dict[str, Any]) -> str:
    return _safe(row.get("marketName") or row.get("name") or row.get("marketType"))


def _american(row: dict[str, Any]) -> float | None:
    candidates = [
        ((row.get("winRunnerOdds") or {}).get("americanDisplayOdds") or {}).get("americanOdds"),
        (row.get("winRunnerOdds") or {}).get("americanOdds"), row.get("americanOdds"), row.get("price"),
    ]
    for value in candidates:
        number = _number(value)
        if number is not None and number != 0 and abs(number) >= 100:
            return number
    return None


def _line(row: dict[str, Any]) -> float | None:
    for key in ("handicap","line","points"):
        number = _number(row.get(key))
        if number is not None:
            return number
    return None


def _runner_name(row: dict[str, Any]) -> str:
    return _safe(row.get("runnerName") or row.get("name") or row.get("selectionName"))


def _market_player_name(name: str) -> str:
    text = re.sub(r"(?i)\s*[-–:]?\s*(player\s+)?passing\s+yards.*$", "", name).strip()
    return text


def _fanduel_markets(game: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        landing = _fd_json(f"{FANDUEL_BASE}/sbapi/content-managed-page", {"_ak":FANDUEL_KEY,"page":"CUSTOM","customPageId":"nfl","timezone":"America/New_York"})
        attachments = landing.get("attachments") or {}
        events = _rows(attachments.get("events")) if isinstance(attachments, dict) else []
        matches = []
        for event in events:
            name = _safe(event.get("name") or event.get("eventName") or event.get("displayName"))
            parts = [p.strip() for p in name.split(" @ ")]
            if len(parts) != 2:
                continue
            if NAME_TO_TEAM.get(parts[0]) == game["away"] and NAME_TO_TEAM.get(parts[1]) == game["home"]:
                event_id = _safe(event.get("eventId") or event.get("id") or event.get("_attachment_key"))
                if event_id:
                    matches.append(event_id)
        if len(set(matches)) != 1:
            return []
        event_id = matches[0]
        payloads = []
        for tab in (None,"passing-props","player-passing-props","player-props","passing"):
            params = {"_ak":FANDUEL_KEY,"eventId":event_id}
            if tab:
                params["tab"] = tab
            payloads.append(_fd_json(f"{FANDUEL_BASE}/sbapi/event-page", params))
        output: dict[tuple[str,float], dict[str, Any]] = {}
        for payload in payloads:
            attach = payload.get("attachments") or {}
            if not isinstance(attach, dict):
                continue
            all_runners = {str(r.get("runnerId") or r.get("id") or r.get("_attachment_key")):r for r in _rows(attach.get("runners"))}
            for market in _rows(attach.get("markets")):
                name = _market_name(market)
                if "passing yards" not in name.casefold():
                    continue
                runners = _rows(market.get("runners"))
                if not runners:
                    ids = market.get("runnerIds") or []
                    runners = [all_runners[str(i)] for i in ids if str(i) in all_runners]
                over = next((r for r in runners if "over" in _runner_name(r).casefold()), None)
                under = next((r for r in runners if "under" in _runner_name(r).casefold()), None)
                if not over or not under:
                    continue
                over_line = _line(over); under_line = _line(under)
                line = over_line if over_line is not None else under_line
                if line is None or (over_line is not None and under_line is not None and abs(over_line-under_line) > 1e-9):
                    continue
                over_odds = _american(over); under_odds = _american(under)
                if over_odds is None or under_odds is None:
                    continue
                player = _market_player_name(name)
                if not player:
                    # Sometimes player is embedded in runner label before Over/Under.
                    label = _runner_name(over)
                    player = re.sub(r"(?i)\s+(over|under).*", "", label).strip()
                if not player:
                    continue
                key = (player.casefold(), float(line))
                output[key] = {
                    "player_name": player, "sportsbook":"FanDuel", "market":"Passing Yards",
                    "line":float(line), "over_odds":over_odds, "under_odds":under_odds,
                    "source_timestamp":_utc_now(), "provider_event_id":event_id,
                }
        return list(output.values())
    except Exception:
        return []


def _history_rows(seasons: list[int], cutoff: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for season in seasons:
        try:
            out.extend(_qb_game_rows(_completed_before(_load_pbp(season), cutoff)))
        except Exception:
            continue
    return out


def _player_bundle(
    *, team: str, opponent: str, side: str, current_rows: list[dict[str, Any]], all_history: list[dict[str, Any]],
    defense: dict[str, Any], frame: pd.DataFrame, markets: list[dict[str, Any]], season: int, week: int | None,
) -> dict[str, Any] | None:
    qb = _select_qb(team, current_rows)
    if not qb:
        return None
    profile = _profile(qb)
    team_attempts_pg, offense_sack_rate = _team_pace(frame, team)
    attempt_inputs = {
        "qb_season_attempts_per_game": profile.get("attempts_per_game"),
        "qb_recent3_attempts": (profile.get("recent3_attempts") / min(3, profile.get("games") or 1)) if profile.get("recent3_attempts") is not None else None,
        "opponent_attempts_allowed_per_game": defense.get("passing_attempts_allowed_per_game"),
        "team_pass_attempts_per_game": team_attempts_pg,
    }
    ypa_inputs = {
        "qb_season_ypa": profile.get("yards_per_attempt"),
        "qb_recent3_ypa": profile.get("recent3_ypa"),
        "opponent_season_ypa_allowed": defense.get("yards_per_attempt_allowed"),
        "opponent_recent3_ypa_allowed": defense.get("recent3_ypa_allowed"),
    }
    step7 = projection_model.project_from_canonical_inputs(attempt_inputs, ypa_inputs)
    step7["qb_name"] = profile.get("qb_name")
    pressure_ready = offense_sack_rate is not None and defense.get("sack_rate_generated") is not None
    pressure = {"ready":pressure_ready,"offense":{"sack_rate_allowed":offense_sack_rate},"defense":{"sack_rate_generated":defense.get("sack_rate_generated")}}
    # Unknown personnel/weather never receives a numerical adjustment in the certified context model.
    personnel = {"qb_status":"No verified hard-status block","personnel_label":"CHECK"}
    environment = {"weather_label":"CHECK", f"{side}_rest":{"turnaround_days":None,"rest_label":"CHECK"}}
    step8 = context_model.build_context_projection(step7, profile, pressure, personnel, environment, side=side, preseason=False)
    step9 = distribution_model.build_distribution(step8)
    market = next((m for m in markets if _safe(m.get("player_name")).casefold() == _safe(profile.get("qb_name")).casefold()), None)
    evaluation = market_model.evaluate_market(
        step9, (market or {}).get("line"), (market or {}).get("over_odds"), (market or {}).get("under_odds"),
        source=(market or {}).get("sportsbook") or "", market_timestamp=(market or {}).get("source_timestamp") or "",
    ) if market else {"ready":False,"grade_ready":False,"lean":"MARKET PENDING","grade":"CHECK","reason":"No verified two-way Passing Yards market available","sportsbook_projection_influence":0.0}
    history = summarize_qb_vs_opponent(all_history, qb_name=str(profile.get("qb_name") or ""), opponent=opponent)
    identity_visuals = build_identity_visuals(
        team=team, opponent=opponent, player_source_id=qb.get("player_source_id"),
        qb_name=str(profile.get("qb_name") or ""), season=int(season), week=week,
    )
    return {
        "team_id":_canonical_team_id(team), "team_abbr":team, "team_name":TEAM_NAMES.get(team,team),
        "opponent_team_id":_canonical_team_id(opponent), "opponent_abbr":opponent, "side":side,
        "player_id":profile.get("player_id"), "qb_name":profile.get("qb_name"), "profile":profile,
        "identity_visuals":identity_visuals,
        "pass_defense":defense, "qb_vs_team_history":history,
        "projection":step7, "context_projection":step8, "distribution":step9, "market":market, "market_evaluation":evaluation,
        "why": {
            "volume": {"value":step7.get("expected_attempts"),"label":"Expected attempts"},
            "efficiency": {"value":step7.get("expected_ypa"),"label":"Expected YPA"},
            "pressure": {"value":step8.get("pressure_adjustment_yards"),"label":"Pressure adjustment yards"},
            "defense": {"value":defense.get("rank"),"label":f"{defense.get('grade','CHECK')} pass matchup"},
        },
    }



def _official_team_logo_url(team: str) -> str:
    return f"{NFL_OFFICIAL_LOGO_BASE}/{canonical_team_abbr(team)}.png"


@lru_cache(maxsize=8)
def _load_nflverse_identity_rows(season: int) -> list[dict[str, Any]]:
    try:
        response = requests.get(NFLVERSE_WEEKLY_ROSTER_URL.format(season=int(season)), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        frame = pd.read_csv(BytesIO(response.content), low_memory=False)
    except Exception:
        return []
    wanted = {"season", "week", "team", "full_name", "gsis_id", "headshot_url"}
    if not wanted.issubset(frame.columns):
        return []
    rows: list[dict[str, Any]] = []
    for _, row in frame[list(wanted)].iterrows():
        gsis_id = _safe(row.get("gsis_id"))
        team = canonical_team_abbr(row.get("team"))
        if not gsis_id or not team:
            continue
        rows.append({
            "season": int(row.get("season")) if _number(row.get("season")) is not None else None,
            "week": int(row.get("week")) if _number(row.get("week")) is not None else None,
            "team": team,
            "full_name": _safe(row.get("full_name")),
            "gsis_id": gsis_id,
            "headshot_url": _safe(row.get("headshot_url")) or None,
        })
    return rows


def build_identity_visuals(
    *, team: str, opponent: str, player_source_id: Any, qb_name: str, season: int, week: int | None,
    roster_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    team = canonical_team_abbr(team)
    opponent = canonical_team_abbr(opponent)
    source_player_id = _safe(player_source_id)
    rows = list(roster_rows) if roster_rows is not None else _load_nflverse_identity_rows(int(season))
    exact = [
        row for row in rows
        if _safe(row.get("gsis_id")) == source_player_id
        and canonical_team_abbr(row.get("team")) == team
        and (_number(row.get("season")) is None or int(float(row.get("season"))) == int(season))
        and (week is None or _number(row.get("week")) is None or int(float(row.get("week"))) == int(week))
    ]
    verified = len(exact) == 1
    matched = exact[0] if verified else {}
    headshot = _safe(matched.get("headshot_url")) or None
    return {
        "canonical_player_id": _canonical_player_id(source_player_id),
        "source_player_id": source_player_id or None,
        "identity_verified": verified,
        "identity_reason": "Exact NFLverse GSIS/team identity verified" if verified else "Exact NFLverse GSIS/team identity unavailable",
        "qb_name": qb_name,
        "headshot_url": headshot if verified else None,
        "headshot_provider": "NFLverse" if verified and headshot else None,
        "team_logo_url": _official_team_logo_url(team),
        "team_logo_provider": "NFL Official",
        "opponent_logo_url": _official_team_logo_url(opponent),
        "opponent_logo_provider": "NFL Official",
    }

def build_page_bundle(target_date: str | None = None) -> dict[str, Any]:
    captured = _utc_now()
    game = _schedule_game(target_date)
    if not game:
        return {"ready":False,"schema_version":SCHEMA_VERSION,"reason":"No verified NFL regular-season game available for requested date","source_timestamp":captured,"games":[]}
    try:
        frame = _completed_before(_load_pbp(game["season"]), game["date"])
    except Exception as exc:
        return {"ready":False,"schema_version":SCHEMA_VERSION,"reason":f"NFL stats unavailable: {type(exc).__name__}","source_timestamp":captured,"games":[game]}
    current_rows = _qb_game_rows(frame)
    defenses = _defense_profiles(frame)
    history = _history_rows(list(range(max(1999, game["season"]-2), game["season"]+1)), game["date"])
    markets = _fanduel_markets(game)
    players = []
    for team, opponent, side in ((game["away"],game["home"],"away"),(game["home"],game["away"],"home")):
        defense = defenses.get(opponent) or {
            "team_id":_canonical_team_id(opponent),"team_abbr":opponent,"team_name":TEAM_NAMES.get(opponent,opponent),
            "rank":None,"grade":"CHECK","pass_yards_allowed_per_game":None,"passing_attempts_allowed_per_game":None,
            "completion_pct_allowed":None,"yards_per_attempt_allowed":None,"recent3_pass_yards_allowed":None,
            "recent3_ypa_allowed":None,"sack_rate_generated":None,
        }
        row = _player_bundle(team=team,opponent=opponent,side=side,current_rows=current_rows,all_history=history,defense=defense,frame=frame,markets=markets,season=game["season"],week=game.get("week"))
        if row:
            players.append(row)
    return {
        "ready": bool(players), "schema_version":SCHEMA_VERSION, "service":"kyre-sports-api",
        "source_timestamp":captured, "game":game, "players":players,
        "provenance": {
            "schedule_stats_history":{"provider":"NFLverse","source_timestamp":captured},
            "market":{"provider":"FanDuel","source_timestamp":max([m.get("source_timestamp","") for m in markets], default=""),"observations":len(markets)},
        },
        "routing": {"gateway":"Kyre Sports API","canonical_ids":True,"sportsbook_line_averaging":False,"missing_to_zero":False,"sportsbook_projection_influence":0.0},
    }


@router.get("")
def nfl_passing_yards_page(date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    return build_page_bundle(date)


__all__ = ["SCHEMA_VERSION","build_identity_visuals","build_page_bundle","nfl_passing_yards_page","pass_defense_grade","router","summarize_qb_vs_opponent"]
