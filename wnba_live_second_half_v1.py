"""WNBA Live Games Step 4 historical second-half / quarter profile engine.

Read-only descriptive layer. V1.1 repairs the historical backfill transport:
ESPN's scoreboard is queried by verified calendar date instead of relying on one
season-wide scoreboard request. Candidate dates come from the official WNBA
season schedule first, with ESPN team schedules as a fallback. Only completed
regular-season games strictly before the live snapshot are accepted.

This module does not read sportsbook prices and cannot change any Step-1/2/3
state, projection, probability, qualification or pick.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_data_v232 as data232

ET = ZoneInfo("America/New_York")
ESPN_SCOREBOARD = data232.ESPN_SCOREBOARD
ESPN_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams"
MODEL_VERSION = "WNBA LIVE SECOND-HALF HISTORY V1.1 • DATE-BACKFILLED"
MAX_TEAM_HISTORY = 20
MAX_WORKERS = 6


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _safe_score(value):
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    try:
        return int(round(float(value)))
    except Exception:
        return None


def _team_id(team: dict) -> int:
    try:
        return int(data232._team_id(team or {}) or 0)
    except Exception:
        return 0


def _regular_season_flag(event: dict, comp: dict | None = None):
    """Return True/False when ESPN exposes season type, else None."""
    comp = comp or {}
    containers = [
        event.get("season") or {},
        comp.get("season") or {},
        event.get("seasonType") or {},
        comp.get("seasonType") or {},
    ]
    for obj in containers:
        if isinstance(obj, (int, float, str)):
            raw = str(obj).strip().lower()
            if raw:
                if raw in {"2", "regular", "regular season", "regular-season"}:
                    return True
                if raw in {"1", "3", "pre", "preseason", "post", "postseason", "playoffs"}:
                    return False
            continue
        if not isinstance(obj, dict):
            continue
        raw_type = obj.get("type")
        if isinstance(raw_type, dict):
            raw_type = raw_type.get("id") or raw_type.get("type") or raw_type.get("name")
        if raw_type is not None and str(raw_type).strip() != "":
            raw = str(raw_type).strip().lower()
            if raw in {"2", "regular", "regular season", "regular-season"}:
                return True
            if raw in {"1", "3", "pre", "preseason", "post", "postseason", "playoffs"}:
                return False
        text = " ".join(
            str(obj.get(k) or "") for k in ("slug", "name", "description", "abbreviation")
        ).lower()
        if text.strip():
            if "regular" in text and "pre" not in text and "post" not in text and "playoff" not in text:
                return True
            if any(x in text for x in ("preseason", "postseason", "playoff")):
                return False
    return None


def _status_completed(event: dict, comp: dict) -> bool:
    status = event.get("status") or comp.get("status") or {}
    stype = status.get("type") or {}
    return bool(stype.get("completed")) or str(stype.get("state") or "").lower() in {"post", "final"}


def _lines(competitor: dict) -> dict[int, int]:
    out = {}
    for idx, item in enumerate(competitor.get("linescores") or [], 1):
        if not isinstance(item, dict):
            continue
        period = _safe_int(item.get("period"), idx)
        score = _safe_score(item.get("displayValue", item.get("value")))
        if period > 0 and score is not None:
            out[period] = score
    return out


def _event_dt(event: dict, comp: dict):
    value = event.get("date") or comp.get("date")
    if not value:
        return None
    try:
        return pd.to_datetime(value, utc=True)
    except Exception:
        return None


def _parse_completed_event(event: dict):
    comps = event.get("competitions") or []
    if not comps:
        return None, "NO_COMP"
    comp = comps[0]
    if not _status_completed(event, comp):
        return None, "NOT_COMPLETE"

    regular = _regular_season_flag(event, comp)
    if regular is False:
        return None, "NON_REGULAR"

    sides = {}
    for c in comp.get("competitors") or []:
        sides[str(c.get("homeAway") or "").lower()] = c
    away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
    away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
    away_id, home_id = _team_id(away_t), _team_id(home_t)
    if not away_id or not home_id:
        return None, "TEAM_ID"

    away_lines, home_lines = _lines(away_c), _lines(home_c)
    if any(p not in away_lines or p not in home_lines for p in (1, 2, 3, 4)):
        return None, "NO_Q_LINES"

    away_score = _safe_score(away_c.get("score"))
    home_score = _safe_score(home_c.get("score"))
    if away_score is None or home_score is None:
        return None, "NO_SCORE"

    dt = _event_dt(event, comp)
    if dt is None:
        return None, "NO_DATE"

    return {
        "event_id": str(event.get("id") or ""),
        "date_utc": dt.isoformat(),
        "game_date_et": dt.tz_convert(ET).strftime("%Y-%m-%d"),
        "away_team_id": away_id,
        "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
        "home_team_id": home_id,
        "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
        "away_score": away_score,
        "home_score": home_score,
        "away_lines": away_lines,
        "home_lines": home_lines,
        "regular_flag": regular,
    }, "OK"


def _espn_day_games(day_str: str):
    day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    meta = {
        "day": day_str,
        "fetched_at": datetime.now(ET).isoformat(),
        "events": 0,
        "accepted": 0,
        "rejected": {},
        "error": "",
    }
    try:
        response = requests.get(
            ESPN_SCOREBOARD,
            params={"dates": pd.to_datetime(day_str).strftime("%Y%m%d"), "limit": 100},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        meta["error"] = str(exc)[:180]
        return [], meta

    rows = []
    events = (payload or {}).get("events") or []
    meta["events"] = len(events)
    for event in events:
        row, reason = _parse_completed_event(event)
        if row is not None:
            rows.append(row)
        else:
            meta["rejected"][reason] = int(meta["rejected"].get(reason, 0)) + 1
    meta["accepted"] = len(rows)
    return rows, meta


@st.cache_data(ttl=3600, show_spinner=False, max_entries=4)
def _espn_team_directory():
    mapping = {}
    error = ""
    try:
        response = requests.get(
            ESPN_TEAMS,
            params={"limit": 100},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        sports = (payload or {}).get("sports") or []
        leagues = sports[0].get("leagues") or [] if sports else []
        teams = leagues[0].get("teams") or [] if leagues else []
        for item in teams:
            team = (item or {}).get("team") or item or {}
            wnba_id = _team_id(team)
            espn_id = str(team.get("id") or "").strip()
            if wnba_id and espn_id:
                mapping[int(wnba_id)] = espn_id
    except Exception as exc:
        error = str(exc)[:180]
    return mapping, error


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _espn_team_schedule_dates(wnba_team_id: int, year: int, cutoff_day: str):
    mapping, directory_error = _espn_team_directory()
    espn_id = mapping.get(int(wnba_team_id))
    meta = {"source": "ESPN team schedule", "dates": 0, "error": directory_error}
    if not espn_id:
        if not meta["error"]:
            meta["error"] = "ESPN team id mapping unavailable"
        return [], meta

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{espn_id}/schedule"
    try:
        response = requests.get(
            url,
            params={"season": int(year), "seasontype": 2, "limit": 100},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        meta["error"] = str(exc)[:180]
        return [], meta

    cutoff_date = pd.to_datetime(cutoff_day).date()
    dates = []
    for event in (payload or {}).get("events") or []:
        comps = event.get("competitions") or []
        comp = comps[0] if comps else {}
        if not _status_completed(event, comp):
            continue
        regular = _regular_season_flag(event, comp)
        if regular is False:
            continue
        dt = _event_dt(event, comp)
        if dt is None:
            continue
        day = dt.tz_convert(ET).date()
        if day > cutoff_date:
            continue
        dates.append(day.strftime("%Y-%m-%d"))
    dates = sorted(set(dates), reverse=True)[:MAX_TEAM_HISTORY]
    meta["dates"] = len(dates)
    return dates, meta


def _official_candidate_dates(team_ids: tuple[int, ...], year: int, cutoff_day: str):
    meta = {"source": "WNBA official season schedule", "dates": 0, "error": ""}
    try:
        schedule = data232._wnba_cdn_schedule()
    except Exception as exc:
        meta["error"] = str(exc)[:180]
        return [], meta
    if schedule is None or schedule.empty:
        meta["error"] = "official season schedule returned empty"
        return [], meta

    frame = schedule.copy()
    frame["game_date"] = pd.to_datetime(frame.get("game_date"), errors="coerce")
    frame = frame.loc[frame["game_date"].dt.year.eq(int(year))].copy()
    cutoff_date = pd.to_datetime(cutoff_day).date()
    frame = frame.loc[frame["game_date"].dt.date <= cutoff_date].copy()
    if "status" in frame.columns:
        frame = frame.loc[frame["status"].astype(str).str.upper().eq("FINAL")].copy()
    if frame.empty:
        meta["error"] = "no completed official games before cutoff"
        return [], meta

    all_dates = set()
    for team_id in team_ids:
        subset = frame.loc[
            frame["away_team_id"].astype(int).eq(int(team_id))
            | frame["home_team_id"].astype(int).eq(int(team_id))
        ].sort_values("game_date", ascending=False).head(MAX_TEAM_HISTORY)
        all_dates.update(subset["game_date"].dt.strftime("%Y-%m-%d").dropna().tolist())

    dates = sorted(all_dates, reverse=True)
    meta["dates"] = len(dates)
    return dates, meta


@st.cache_data(ttl=900, show_spinner=False, max_entries=12)
def _season_games(year: int, team_ids: tuple[int, ...], cutoff_day: str):
    """Backfill recent completed regular-season games for the requested teams."""
    fetched_at = datetime.now(ET).isoformat()
    meta = {
        "fetched_at": fetched_at,
        "source": "WNBA official schedule → ESPN daily scoreboards",
        "error": "",
        "games": 0,
        "dates_requested": 0,
        "dates_ok": 0,
        "candidate_source": "",
        "daily_errors": 0,
        "rejected": {},
    }

    clean_ids = tuple(sorted({int(x) for x in team_ids if int(x) > 0}))
    dates, source_meta = _official_candidate_dates(clean_ids, int(year), cutoff_day)
    meta["candidate_source"] = source_meta.get("source") or ""

    if not dates:
        fallback_dates = set()
        fallback_errors = []
        for team_id in clean_ids:
            td, tm = _espn_team_schedule_dates(team_id, int(year), cutoff_day)
            fallback_dates.update(td)
            if tm.get("error"):
                fallback_errors.append(str(tm["error"]))
        dates = sorted(fallback_dates, reverse=True)
        meta["candidate_source"] = "ESPN team schedule fallback"
        if not dates and fallback_errors:
            meta["error"] = " | ".join(fallback_errors)[:220]

    meta["dates_requested"] = len(dates)
    if not dates:
        if not meta["error"]:
            meta["error"] = source_meta.get("error") or "no historical candidate dates"
        return [], meta

    rows = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(dates)))) as pool:
        futures = {pool.submit(_espn_day_games, day): day for day in dates}
        for future in as_completed(futures):
            try:
                day_rows, day_meta = future.result()
            except Exception as exc:
                day_rows, day_meta = [], {"error": str(exc)[:180], "rejected": {}}
            if not day_meta.get("error"):
                meta["dates_ok"] += 1
            else:
                meta["daily_errors"] += 1
            for reason, count in (day_meta.get("rejected") or {}).items():
                meta["rejected"][reason] = int(meta["rejected"].get(reason, 0)) + int(count)
            rows.extend(day_rows)

    dedup = {}
    for row in rows:
        if clean_ids and int(row.get("away_team_id") or 0) not in clean_ids and int(row.get("home_team_id") or 0) not in clean_ids:
            continue
        key = str(row.get("event_id") or "") or (
            f"{row.get('date_utc')}:{row.get('away_team_id')}:{row.get('home_team_id')}"
        )
        dedup[key] = row

    rows = sorted(dedup.values(), key=lambda r: r["date_utc"], reverse=True)
    meta["games"] = len(rows)
    if not rows and not meta["error"]:
        meta["error"] = (
            "historical dates were found but ESPN daily scoreboards returned no "
            "completed four-quarter WNBA rows"
        )
    return rows, meta


def clear_cache():
    for fn in (_season_games, _espn_team_directory, _espn_team_schedule_dates):
        try:
            fn.clear()
        except Exception:
            pass


def _team_rows(team_id: int, season_rows: list[dict], cutoff, exclude_event_id: str = ""):
    out = []
    cutoff_ts = pd.to_datetime(cutoff, utc=True) if cutoff is not None else pd.Timestamp.now(tz="UTC")
    for g in season_rows:
        if exclude_event_id and str(g.get("event_id") or "") == str(exclude_event_id):
            continue
        dt = pd.to_datetime(g.get("date_utc"), utc=True, errors="coerce")
        if pd.isna(dt) or dt >= cutoff_ts:
            continue
        is_away = int(g.get("away_team_id") or 0) == int(team_id)
        is_home = int(g.get("home_team_id") or 0) == int(team_id)
        if not (is_away or is_home):
            continue

        if is_away:
            own, opp = g["away_lines"], g["home_lines"]
            own_final, opp_final = g["away_score"], g["home_score"]
            opp_name = g["home_team"]
            venue = "AWAY"
        else:
            own, opp = g["home_lines"], g["away_lines"]
            own_final, opp_final = g["home_score"], g["away_score"]
            opp_name = g["away_team"]
            venue = "HOME"

        h1_for, h1_against = own[1] + own[2], opp[1] + opp[2]
        q3_for, q3_against = own[3], opp[3]
        q4_for, q4_against = own[4], opp[4]
        h2_for, h2_against = q3_for + q4_for, q3_against + q4_against

        out.append({
            "date": g["game_date_et"],
            "opponent": opp_name,
            "venue": venue,
            "q3_for": q3_for, "q3_against": q3_against,
            "q4_for": q4_for, "q4_against": q4_against,
            "h2_for": h2_for, "h2_against": h2_against,
            "h2_margin": h2_for - h2_against,
            "halftime_margin": h1_for - h1_against,
            "final_margin": own_final - opp_final,
            "won": own_final > opp_final,
        })
    return out


def _avg(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _rate(num, den):
    return (float(num) / float(den)) if den else None


def _reliability(n: int) -> str:
    if n >= 15:
        return "HIGH"
    if n >= 8:
        return "MEDIUM"
    if n >= 4:
        return "LOW"
    return "THIN"


def profile(team_id: int, season_rows: list[dict], cutoff, current_role: str, exclude_event_id: str = ""):
    rows = _team_rows(team_id, season_rows, cutoff, exclude_event_id)
    recent10, recent5 = rows[:10], rows[:5]
    role_rows = [r for r in rows if r.get("venue") == str(current_role).upper()]

    led = [r for r in rows if r["halftime_margin"] > 0]
    trailed = [r for r in rows if r["halftime_margin"] < 0]
    tied = [r for r in rows if r["halftime_margin"] == 0]

    q3_for = _avg(rows, "q3_for")
    q3_against = _avg(rows, "q3_against")
    q4_for = _avg(rows, "q4_for")
    q4_against = _avg(rows, "q4_against")

    return {
        "games": len(rows),
        "reliability": _reliability(len(rows)),
        "q3_for": q3_for,
        "q3_against": q3_against,
        "q3_margin": (q3_for - q3_against) if q3_for is not None and q3_against is not None else None,
        "q4_for": q4_for,
        "q4_against": q4_against,
        "q4_margin": (q4_for - q4_against) if q4_for is not None and q4_against is not None else None,
        "h2_for": _avg(rows, "h2_for"),
        "h2_against": _avg(rows, "h2_against"),
        "h2_margin": _avg(rows, "h2_margin"),
        "h2_win_rate": _rate(sum(1 for r in rows if r["h2_margin"] > 0), len(rows)),
        "l10_h2_margin": _avg(recent10, "h2_margin"),
        "l5_h2_margin": _avg(recent5, "h2_margin"),
        "venue_h2_margin": _avg(role_rows, "h2_margin"),
        "venue_games": len(role_rows),
        "lead_hold_rate": _rate(sum(1 for r in led if r["won"]), len(led)),
        "lead_sample": len(led),
        "comeback_rate": _rate(sum(1 for r in trailed if r["won"]), len(trailed)),
        "trail_sample": len(trailed),
        "tied_half_games": len(tied),
        "last5": recent5,
    }


def profiles_for_game(game: dict, season: int | None = None):
    captured = pd.to_datetime(game.get("captured_at") or datetime.now(ET).isoformat(), utc=True)
    year = int(season or captured.tz_convert(ET).year)
    cutoff_day = captured.tz_convert(ET).strftime("%Y-%m-%d")
    event_id = str(game.get("espn_event_id") or "")
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    team_ids = tuple(x for x in (away_id, home_id) if x)
    rows, meta = _season_games(year, team_ids, cutoff_day)
    cutoff = game.get("captured_at") or datetime.now(ET).isoformat()
    return {
        "away": profile(away_id, rows, cutoff, "AWAY", event_id) if away_id else {},
        "home": profile(home_id, rows, cutoff, "HOME", event_id) if home_id else {},
        "meta": meta,
    }
