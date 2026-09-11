"""NFL Passing Yards Step 3 — opponent pass-defense matchup context.

This layer adds descriptive opponent passing-defense evidence only. It does not
create or alter a passing-yards projection, probability, sportsbook grade, fair
line, EV, Monte Carlo result, ranking, or recommendation.

Primary source: ESPN Core NFL team season statistics.
Recent-form source: ESPN team schedule + ESPN game summary box score.
The selected matchup's verified ESPN team IDs are reused; no fuzzy team matching
or name-based identity recovery is permitted.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import math
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

MODEL_VERSION = "NFL PASSING YARDS STEP 3 • OPPONENT PASS DEFENSE V1"
CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _safe(value).lower())


def _json_get(url: str, timeout: int = 8):
    diag = {"url": url, "http": None, "ok": False, "error": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        diag["http"] = int(r.status_code)
        r.raise_for_status()
        payload = r.json()
        diag["ok"] = True
        return payload, diag
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return {}, diag


@st.cache_data(ttl=300, show_spinner=False)
def _team_stats_payload(year: int, season_type: int, team_id: str):
    team_id = _safe(team_id)
    if not team_id or not team_id.isdigit():
        return {}, {"ok": False, "http": None, "error": "missing verified ESPN team id"}
    url = f"{CORE_BASE}/seasons/{int(year)}/types/{int(season_type)}/teams/{team_id}/statistics"
    return _json_get(url)


@st.cache_data(ttl=300, show_spinner=False)
def _team_schedule_payload(year: int, season_type: int, team_id: str):
    team_id = _safe(team_id)
    if not team_id or not team_id.isdigit():
        return {}, {"ok": False, "http": None, "error": "missing verified ESPN team id"}
    url = f"{SITE_BASE}/teams/{team_id}/schedule?season={int(year)}&seasontype={int(season_type)}"
    return _json_get(url)


@st.cache_data(ttl=300, show_spinner=False)
def _summary_payload(event_id: str):
    event_id = _safe(event_id)
    if not event_id or not event_id.isdigit():
        return {}, {"ok": False, "http": None, "error": "invalid ESPN event id"}
    return _json_get(f"{SITE_BASE}/summary?event={event_id}")


def _flatten_stats(payload: dict) -> dict[str, dict]:
    """Flatten ESPN team split categories while preserving rank/per-game fields."""
    splits = (payload or {}).get("splits") or {}
    categories = splits.get("categories") if isinstance(splits, dict) else None
    if not isinstance(categories, list):
        categories = (payload or {}).get("categories") or []
    out: dict[str, dict] = {}
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        for stat in cat.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            keys = {
                _norm(stat.get("name")),
                _norm(stat.get("displayName")),
                _norm(stat.get("shortDisplayName")),
                _norm(stat.get("abbreviation")),
            }
            row = dict(stat)
            for key in keys:
                if key:
                    out[key] = row
    return out


def _pick_row(stats: dict[str, dict], aliases: tuple[str, ...]) -> dict:
    for alias in aliases:
        key = _norm(alias)
        if key in stats:
            return stats[key]
    return {}


def _row_value(row: dict, prefer_per_game: bool = False):
    if not row:
        return math.nan
    fields = ("perGameValue", "value", "displayValue") if prefer_per_game else ("value", "perGameValue", "displayValue")
    for field in fields:
        value = _num(row.get(field))
        if _finite(value):
            return value
    return math.nan


def _row_rank(row: dict):
    value = _num((row or {}).get("rank"))
    return int(value) if _finite(value) and value > 0 else None


def parse_season_pass_defense(payload: dict) -> dict:
    """Parse only opponent/defensive passing stats; never substitutes offensive stats."""
    stats = _flatten_stats(payload)
    games_row = _pick_row(stats, ("gamesPlayed", "games", "GP"))
    yards_row = _pick_row(stats, (
        "passingYardsAllowed", "opponentPassingYards", "oppPassingYards",
        "passYardsAllowed", "netPassingYardsAllowed", "opponentNetPassingYards",
    ))
    attempts_row = _pick_row(stats, ("opponentPassingAttempts", "passingAttemptsAllowed", "passAttemptsAllowed", "oppPassAttempts"))
    completions_row = _pick_row(stats, ("opponentPassingCompletions", "passingCompletionsAllowed", "completionsAllowed", "oppPassCompletions"))
    td_row = _pick_row(stats, ("opponentPassingTouchdowns", "passingTouchdownsAllowed", "passTouchdownsAllowed", "oppPassTouchdowns"))
    int_row = _pick_row(stats, ("interceptions", "defensiveInterceptions", "passesIntercepted", "opponentPassingInterceptions"))
    sack_row = _pick_row(stats, ("sacks", "totalSacks", "defensiveSacks", "opponentTimesSacked"))
    pct_row = _pick_row(stats, ("opponentCompletionPercentage", "completionPctAllowed", "completionPercentageAllowed"))
    ypa_row = _pick_row(stats, ("opponentPassingYardsPerAttempt", "passingYardsPerAttemptAllowed", "yardsPerAttemptAllowed"))

    games = _row_value(games_row)
    yards_total = _row_value(yards_row)
    attempts = _row_value(attempts_row)
    completions = _row_value(completions_row)
    pass_tds = _row_value(td_row)
    interceptions = _row_value(int_row)
    sacks = _row_value(sack_row)
    completion_pct = _row_value(pct_row)
    ypa = _row_value(ypa_row)

    yards_per_game = _row_value(yards_row, prefer_per_game=True)
    if (not _finite(yards_per_game) or yards_per_game == yards_total) and _finite(yards_total) and _finite(games) and games > 0:
        yards_per_game = yards_total / games
    attempts_per_game = attempts / games if _finite(attempts) and _finite(games) and games > 0 else math.nan
    completions_per_game = completions / games if _finite(completions) and _finite(games) and games > 0 else math.nan
    if not _finite(completion_pct) and _finite(completions) and _finite(attempts) and attempts > 0:
        completion_pct = 100.0 * completions / attempts
    if not _finite(ypa) and _finite(yards_total) and _finite(attempts) and attempts > 0:
        ypa = yards_total / attempts

    rank = _row_rank(yards_row)
    ready = _finite(yards_per_game) and _finite(attempts) and attempts > 0
    return {
        "ready": bool(ready),
        "games": games,
        "passing_yards_allowed": yards_total,
        "passing_yards_allowed_per_game": yards_per_game,
        "passing_attempts_allowed": attempts,
        "passing_attempts_allowed_per_game": attempts_per_game,
        "passing_completions_allowed": completions,
        "passing_completions_allowed_per_game": completions_per_game,
        "completion_pct_allowed": completion_pct,
        "yards_per_attempt_allowed": ypa,
        "passing_tds_allowed": pass_tds,
        "interceptions": interceptions,
        "sacks": sacks,
        "passing_yards_allowed_rank": rank,
    }


def _completed_event_rows(payload: dict, cutoff_date: str, max_games: int = 5) -> list[dict]:
    cutoff = pd.to_datetime(cutoff_date, errors="coerce")
    rows = []
    for event in (payload or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _safe(event.get("id"))
        event_date = pd.to_datetime(event.get("date"), errors="coerce")
        competitions = event.get("competitions") or []
        comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
        status = ((comp.get("status") or {}).get("type") or {}) if isinstance(comp, dict) else {}
        completed = bool(status.get("completed")) or _safe(status.get("state")).lower() == "post"
        if not event_id.isdigit() or pd.isna(event_date) or not completed:
            continue
        if pd.notna(cutoff) and event_date.normalize() >= cutoff.normalize():
            continue
        rows.append({"event_id": event_id, "date": event_date})
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows[: max(0, int(max_games))]


def _team_boxscore_row(summary: dict, team_id: str) -> dict:
    for team in ((summary or {}).get("boxscore") or {}).get("teams") or []:
        if not isinstance(team, dict):
            continue
        ident = _safe((team.get("team") or {}).get("id"))
        if ident == _safe(team_id):
            return team
    return {}


def _box_stat(team_row: dict, aliases: tuple[str, ...]):
    lookup = {}
    for item in (team_row or {}).get("statistics") or []:
        if not isinstance(item, dict):
            continue
        for key in (_norm(item.get("name")), _norm(item.get("label")), _norm(item.get("abbreviation"))):
            if key:
                lookup[key] = item
    for alias in aliases:
        row = lookup.get(_norm(alias))
        if row:
            return row.get("value") if row.get("value") is not None else row.get("displayValue")
    return None


def parse_recent_defense_game(summary: dict, defense_team_id: str) -> dict:
    """Use the opponent box-score row to describe what this defense allowed."""
    teams = ((summary or {}).get("boxscore") or {}).get("teams") or []
    opponent = None
    for row in teams:
        if not isinstance(row, dict):
            continue
        if _safe((row.get("team") or {}).get("id")) != _safe(defense_team_id):
            opponent = row
            break
    if not opponent:
        return {}
    yards = _num(_box_stat(opponent, ("passingYards", "Pass Yards", "netPassingYards")))
    comp_att = _safe(_box_stat(opponent, ("completionAttempts", "completionsAttempts", "C/ATT", "Comp-Att")))
    completions = attempts = math.nan
    if "/" in comp_att:
        left, right = comp_att.split("/", 1)
        completions, attempts = _num(left), _num(right)
    elif "-" in comp_att:
        left, right = comp_att.split("-", 1)
        completions, attempts = _num(left), _num(right)
    if not _finite(yards):
        return {}
    return {
        "passing_yards_allowed": yards,
        "completions_allowed": completions,
        "attempts_allowed": attempts,
        "completion_pct_allowed": (100.0 * completions / attempts) if _finite(completions) and _finite(attempts) and attempts > 0 else math.nan,
        "yards_per_attempt_allowed": (yards / attempts) if _finite(attempts) and attempts > 0 else math.nan,
    }


def _avg(rows: list[dict], key: str):
    values = [_num(row.get(key)) for row in rows]
    values = [x for x in values if _finite(x)]
    return sum(values) / len(values) if values else math.nan


def _recent_form(team_id: str, year: int, season_type: int, cutoff_date: str) -> tuple[list[dict], dict]:
    schedule, schedule_diag = _team_schedule_payload(year, season_type, team_id)
    if not schedule_diag.get("ok"):
        return [], {"schedule_http": schedule_diag.get("http"), "summary_ok": 0}
    events = _completed_event_rows(schedule, cutoff_date, max_games=5)
    rows = []
    if events:
        with ThreadPoolExecutor(max_workers=min(5, len(events))) as pool:
            future_map = {pool.submit(_summary_payload, row["event_id"]): row for row in events}
            for future in as_completed(future_map):
                meta = future_map[future]
                try:
                    summary, diag = future.result()
                except Exception:
                    continue
                parsed = parse_recent_defense_game(summary, team_id) if diag.get("ok") else {}
                if parsed:
                    parsed["event_id"] = meta["event_id"]
                    parsed["date"] = meta["date"].strftime("%Y-%m-%d")
                    rows.append(parsed)
    rows.sort(key=lambda x: x.get("date", ""), reverse=True)
    return rows, {"schedule_http": schedule_diag.get("http"), "summary_ok": len(rows)}


def matchup_grade(season: dict) -> tuple[str, str]:
    """League-relative label only when ESPN supplies a rank; otherwise fail closed."""
    rank = season.get("passing_yards_allowed_rank")
    try:
        rank = int(rank)
    except Exception:
        return "CHECK", "ESPN pass-defense rank unavailable"
    if 1 <= rank <= 8:
        return "TOUGH", f"ESPN pass-yards-allowed rank #{rank}"
    if 25 <= rank <= 32:
        return "FAVORABLE", f"ESPN pass-yards-allowed rank #{rank}"
    if 9 <= rank <= 24:
        return "BALANCED", f"ESPN pass-yards-allowed rank #{rank}"
    return "CHECK", "ESPN pass-defense rank invalid"


def build_pass_defense_profile(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str) -> dict:
    team_id = _safe(team_id)
    team_name = _safe(team_name, "Opponent")
    if not team_id.isdigit():
        return {"ready": False, "reason": "missing verified opponent ESPN team ID", "team_id": team_id, "team_name": team_name}

    payload, diag = _team_stats_payload(year, season_type, team_id)
    season = parse_season_pass_defense(payload) if diag.get("ok") else {"ready": False}
    recent, recent_diag = _recent_form(team_id, year, season_type, cutoff_date)
    grade, grade_basis = matchup_grade(season)
    return {
        "ready": bool(season.get("ready")),
        "reason": "" if season.get("ready") else "verified opponent passing-defense totals are incomplete",
        "team_id": team_id,
        "team_name": team_name,
        "season": season,
        "recent_games": recent,
        "recent3_yards_allowed": _avg(recent[:3], "passing_yards_allowed"),
        "recent5_yards_allowed": _avg(recent[:5], "passing_yards_allowed"),
        "recent3_completion_pct_allowed": _avg(recent[:3], "completion_pct_allowed"),
        "recent3_ypa_allowed": _avg(recent[:3], "yards_per_attempt_allowed"),
        "matchup_grade": grade,
        "grade_basis": grade_basis,
        "stats_http": diag.get("http"),
        "schedule_http": recent_diag.get("schedule_http"),
        "recent_verified_games": recent_diag.get("summary_ok", 0),
    }


__all__ = [
    "MODEL_VERSION",
    "build_pass_defense_profile",
    "matchup_grade",
    "parse_recent_defense_game",
    "parse_season_pass_defense",
]
