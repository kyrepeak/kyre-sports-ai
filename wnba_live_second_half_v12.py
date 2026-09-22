"""WNBA Live Step 4 history transport V1.2.

Repairs the zero-history failure seen on Streamlit by no longer depending on
historical ESPN daily-scoreboard rows to contain quarter linescores. Recent
completed regular-season event IDs are discovered from each team's ESPN
regular-season schedule, then each event is fetched through ESPN's summary
endpoint (the same endpoint already proven by Live Step 3). Quarter scores are
parsed from the summary header and converted into the exact row contract used by
wnba_live_second_half_v1.profile().

Read-only descriptive layer. No sportsbook input, projection, probability,
Monte Carlo, edge, EV, qualification or pick is created here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_live_second_half_v1 as base
import wnba_live_flow_v1 as flow

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE SECOND-HALF HISTORY V1.2 • SUMMARY BACKFILL"
MAX_EVENTS_PER_TEAM = 20
MAX_WORKERS = 8


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _event_dt(event: dict, comp: dict):
    value = event.get("date") or comp.get("date")
    if not value:
        return None
    try:
        return pd.to_datetime(value, utc=True)
    except Exception:
        return None


def _completed(event: dict, comp: dict) -> bool:
    status = event.get("status") or comp.get("status") or {}
    stype = status.get("type") or {}
    return bool(stype.get("completed")) or str(stype.get("state") or "").lower() in {"post", "final"}


def _regular_flag(event: dict, comp: dict):
    try:
        return base._regular_season_flag(event, comp)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _team_schedule_events(wnba_team_id: int, year: int, cutoff_day: str):
    """Return recent completed regular-season ESPN event ids for one WNBA team."""
    mapping, directory_error = base._espn_team_directory()
    espn_id = mapping.get(int(wnba_team_id))
    meta = {
        "source": "ESPN team schedule • seasontype=2",
        "team_id": int(wnba_team_id),
        "espn_team_id": str(espn_id or ""),
        "events": 0,
        "error": str(directory_error or ""),
    }
    if not espn_id:
        if not meta["error"]:
            meta["error"] = "ESPN team id mapping unavailable"
        return [], meta

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{espn_id}/schedule"
    try:
        response = requests.get(
            url,
            params={"season": int(year), "seasontype": 2, "limit": 100},
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
            timeout=9,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        meta["error"] = str(exc)[:220]
        return [], meta

    cutoff = pd.to_datetime(cutoff_day).date()
    rows = []
    for event in (payload or {}).get("events") or []:
        comps = event.get("competitions") or []
        comp = comps[0] if comps else {}
        if not _completed(event, comp):
            continue
        regular = _regular_flag(event, comp)
        if regular is False:
            continue
        dt = _event_dt(event, comp)
        if dt is None:
            continue
        game_day = dt.tz_convert(ET).date()
        if game_day > cutoff:
            continue
        event_id = str(event.get("id") or comp.get("id") or "").strip()
        if not event_id:
            continue
        rows.append({"event_id": event_id, "date_utc": dt.isoformat(), "date_et": game_day.strftime("%Y-%m-%d")})

    dedup = {r["event_id"]: r for r in rows}
    rows = sorted(dedup.values(), key=lambda r: r["date_utc"], reverse=True)[:MAX_EVENTS_PER_TEAM]
    meta["events"] = len(rows)
    return rows, meta


@st.cache_data(ttl=1800, show_spinner=False, max_entries=160)
def _summary(event_id: str):
    meta = {"event_id": str(event_id), "http": None, "error": "", "available": False}
    try:
        response = requests.get(
            flow.ESPN_SUMMARY,
            params={"event": str(event_id)},
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
            timeout=9,
        )
        meta["http"] = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
        meta["available"] = isinstance(payload, dict)
        return payload if isinstance(payload, dict) else {}, meta
    except Exception as exc:
        meta["error"] = str(exc)[:220]
        return {}, meta


def _summary_comp(payload: dict):
    header = (payload or {}).get("header") or {}
    comps = header.get("competitions") or []
    if comps:
        return header, comps[0]
    # Defensive fallback for payload variants.
    comps = (payload or {}).get("competitions") or []
    return header, (comps[0] if comps else {})


def _parse_summary(payload: dict, fallback_event_id: str = ""):
    header, comp = _summary_comp(payload)
    if not comp:
        return None, "NO_COMP"

    competitors = comp.get("competitors") or []
    sides = {}
    for c in competitors:
        sides[str(c.get("homeAway") or "").lower()] = c
    away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
    away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
    away_id, home_id = base._team_id(away_t), base._team_id(home_t)
    if not away_id or not home_id:
        return None, "TEAM_ID"

    away_lines, home_lines = base._lines(away_c), base._lines(home_c)
    if any(p not in away_lines or p not in home_lines for p in (1, 2, 3, 4)):
        return None, "NO_Q_LINES"

    away_score = base._safe_score(away_c.get("score"))
    home_score = base._safe_score(home_c.get("score"))
    if away_score is None or home_score is None:
        # Summary headers occasionally omit the final total; regulation quarter
        # lines are sufficient to reconstruct it for non-OT and are still useful
        # for the second-half profile. Include OT lines when present.
        away_score = sum(int(v) for _, v in sorted(away_lines.items()))
        home_score = sum(int(v) for _, v in sorted(home_lines.items()))

    value = header.get("date") or comp.get("date")
    try:
        dt = pd.to_datetime(value, utc=True)
    except Exception:
        return None, "NO_DATE"

    event_id = str(header.get("id") or comp.get("id") or fallback_event_id or "")
    return {
        "event_id": event_id,
        "date_utc": dt.isoformat(),
        "game_date_et": dt.tz_convert(ET).strftime("%Y-%m-%d"),
        "away_team_id": int(away_id),
        "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
        "home_team_id": int(home_id),
        "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
        "away_score": int(away_score),
        "home_score": int(home_score),
        "away_lines": away_lines,
        "home_lines": home_lines,
    }, "OK"


@st.cache_data(ttl=900, show_spinner=False, max_entries=16)
def _summary_history(year: int, team_ids: tuple[int, ...], cutoff_day: str, exclude_event_id: str = ""):
    fetched_at = datetime.now(ET).isoformat()
    clean_ids = tuple(sorted({int(x) for x in team_ids if int(x) > 0}))
    meta = {
        "fetched_at": fetched_at,
        "source": "ESPN regular-season team schedules → ESPN event summaries",
        "error": "",
        "games": 0,
        "candidate_events": 0,
        "summaries_ok": 0,
        "summary_errors": 0,
        "rejected": {},
        "team_schedule_errors": [],
    }

    candidates = {}
    for team_id in clean_ids:
        events, tm = _team_schedule_events(team_id, int(year), cutoff_day)
        if tm.get("error"):
            meta["team_schedule_errors"].append(str(tm.get("error")))
        for item in events:
            if str(item.get("event_id") or "") == str(exclude_event_id or ""):
                continue
            candidates[str(item["event_id"])] = item

    meta["candidate_events"] = len(candidates)
    if not candidates:
        meta["error"] = "no completed regular-season event ids returned by ESPN team schedules"
        return [], meta

    parsed_rows = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(candidates)))) as pool:
        futures = {pool.submit(_summary, event_id): event_id for event_id in candidates}
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                payload, sm = future.result()
            except Exception as exc:
                payload, sm = {}, {"error": str(exc)[:180]}
            if sm.get("error"):
                meta["summary_errors"] += 1
                continue
            row, reason = _parse_summary(payload, event_id)
            if row is None:
                meta["rejected"][reason] = int(meta["rejected"].get(reason, 0)) + 1
                continue
            if clean_ids and int(row.get("away_team_id") or 0) not in clean_ids and int(row.get("home_team_id") or 0) not in clean_ids:
                meta["rejected"]["NOT_TARGET_TEAM"] = int(meta["rejected"].get("NOT_TARGET_TEAM", 0)) + 1
                continue
            parsed_rows.append(row)
            meta["summaries_ok"] += 1

    dedup = {}
    for row in parsed_rows:
        key = str(row.get("event_id") or "") or f"{row.get('date_utc')}:{row.get('away_team_id')}:{row.get('home_team_id')}"
        dedup[key] = row
    rows = sorted(dedup.values(), key=lambda r: r["date_utc"], reverse=True)
    meta["games"] = len(rows)
    if not rows:
        parts = ["summary backfill returned zero usable four-quarter games"]
        if meta["team_schedule_errors"]:
            parts.append("team schedule: " + " | ".join(meta["team_schedule_errors"])[:120])
        if meta["rejected"]:
            parts.append("rejected=" + str(meta["rejected"]))
        meta["error"] = " • ".join(parts)[:300]
    return rows, meta


def profiles_for_game(game: dict, season: int | None = None):
    captured = pd.to_datetime(game.get("captured_at") or datetime.now(ET).isoformat(), utc=True)
    year = int(season or captured.tz_convert(ET).year)
    cutoff_day = captured.tz_convert(ET).strftime("%Y-%m-%d")
    event_id = str(game.get("espn_event_id") or "")
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    team_ids = tuple(x for x in (away_id, home_id) if x)

    rows, meta = _summary_history(year, team_ids, cutoff_day, event_id)

    # Last-resort compatibility fallback. It is intentionally secondary because
    # V1.1's daily-scoreboard transport is the path that produced the zero-game
    # failure on Streamlit.
    if not rows:
        try:
            old_rows, old_meta = base._season_games(year, team_ids, cutoff_day)
        except Exception:
            old_rows, old_meta = [], {}
        if old_rows:
            rows = old_rows
            meta = {**meta, "source": "V1.1 daily-scoreboard fallback", "error": "", "games": len(rows), "fallback_meta": old_meta}

    cutoff = game.get("captured_at") or datetime.now(ET).isoformat()
    return {
        "away": base.profile(away_id, rows, cutoff, "AWAY", event_id) if away_id else {},
        "home": base.profile(home_id, rows, cutoff, "HOME", event_id) if home_id else {},
        "meta": meta,
    }


def clear_cache():
    for fn in (_team_schedule_events, _summary, _summary_history):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        base.clear_cache()
    except Exception:
        pass


# Compatibility exports used by the existing Step-4 renderer.
profile = base.profile
_reliability = base._reliability
