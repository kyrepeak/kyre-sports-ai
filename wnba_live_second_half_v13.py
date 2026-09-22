"""WNBA Live Step 4 history transport V1.3.

Repairs the remaining zero-candidate failure from V1.2. ESPN's team-schedule
endpoint is no longer used to discover historical event ids. Instead:

1) the official WNBA CDN season schedule supplies the recent dates for each team;
2) each official date is expanded by +/- 1 day to protect against UTC/ET date drift;
3) ESPN's proven date-specific WNBA scoreboard supplies the matching completed
   event id for that team;
4) ESPN summary supplies Q1-Q4 linescores for the historical profile.

Read-only descriptive layer. No sportsbook input, projection, probability,
Monte Carlo, edge, EV, qualification or pick is created here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_data_v232 as data232
import wnba_live_second_half_v12 as old

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE SECOND-HALF HISTORY V1.3 • OFFICIAL-DATE BACKFILL"
MAX_EVENTS_PER_TEAM = 20
MAX_WORKERS = 8


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _completed(event: dict, comp: dict) -> bool:
    status = event.get("status") or comp.get("status") or {}
    stype = status.get("type") or {}
    return bool(stype.get("completed")) or str(stype.get("state") or "").lower() in {"post", "final"}


def _event_dt(event: dict, comp: dict):
    value = event.get("date") or comp.get("date")
    if not value:
        return None
    try:
        return pd.to_datetime(value, utc=True)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=96)
def _espn_day_events(day_str: str):
    """Completed WNBA event identities for one ET calendar date."""
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    meta = {"day": day, "events": 0, "completed": 0, "error": ""}
    try:
        response = requests.get(
            data232.ESPN_SCOREBOARD,
            params={"dates": pd.to_datetime(day).strftime("%Y%m%d"), "limit": 100},
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        meta["error"] = str(exc)[:200]
        return [], meta

    rows = []
    events = (payload or {}).get("events") or []
    meta["events"] = len(events)
    for event in events:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        if not _completed(event, comp):
            continue
        sides = {}
        for c in comp.get("competitors") or []:
            sides[str(c.get("homeAway") or "").lower()] = c
        away_t = (sides.get("away") or {}).get("team") or {}
        home_t = (sides.get("home") or {}).get("team") or {}
        away_id = int(data232._team_id(away_t) or 0)
        home_id = int(data232._team_id(home_t) or 0)
        if not away_id or not home_id:
            continue
        event_id = str(event.get("id") or comp.get("id") or "").strip()
        dt = _event_dt(event, comp)
        if not event_id or dt is None:
            continue
        rows.append({
            "event_id": event_id,
            "date_utc": dt.isoformat(),
            "date_et": dt.tz_convert(ET).strftime("%Y-%m-%d"),
            "away_team_id": away_id,
            "home_team_id": home_id,
        })
    meta["completed"] = len(rows)
    return rows, meta


def _official_team_dates(wnba_team_id: int, year: int, cutoff_day: str):
    meta = {"source": "WNBA official CDN schedule", "schedule_rows": 0, "dates": 0, "error": ""}
    try:
        frame = data232._wnba_cdn_schedule()
    except Exception as exc:
        meta["error"] = str(exc)[:220]
        return [], meta
    if frame is None or frame.empty:
        meta["error"] = "official WNBA schedule returned empty"
        return [], meta

    work = frame.copy()
    work["game_date"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    work = work.loc[work["game_date"].notna()].copy()
    work = work.loc[work["game_date"].dt.year.eq(int(year))].copy()
    target = int(wnba_team_id)
    work = work.loc[
        work["away_team_id"].astype(int).eq(target)
        | work["home_team_id"].astype(int).eq(target)
    ].copy()
    cutoff = pd.to_datetime(cutoff_day).date()
    work = work.loc[work["game_date"].dt.date <= cutoff].copy()
    work = work.sort_values("game_date", ascending=False).head(MAX_EVENTS_PER_TEAM)
    meta["schedule_rows"] = len(work)
    dates = work["game_date"].dt.strftime("%Y-%m-%d").dropna().tolist()
    meta["dates"] = len(dates)
    return dates, meta


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _team_schedule_events(wnba_team_id: int, year: int, cutoff_day: str):
    """Discover recent completed ESPN event ids from official WNBA game dates."""
    official_dates, official_meta = _official_team_dates(int(wnba_team_id), int(year), cutoff_day)
    meta = {
        "source": "WNBA official dates → ESPN daily scoreboard",
        "team_id": int(wnba_team_id),
        "official_dates": len(official_dates),
        "query_dates": 0,
        "scoreboard_ok": 0,
        "scoreboard_errors": 0,
        "events": 0,
        "error": str(official_meta.get("error") or ""),
    }
    if not official_dates:
        if not meta["error"]:
            meta["error"] = "no official WNBA dates found for team before cutoff"
        return [], meta

    # WNBA CDN game_date can be derived from a UTC timestamp on some transports.
    # Search the official date plus one day on each side so late-night games cannot
    # disappear because of UTC/ET rollover.
    query_dates = set()
    for text in official_dates:
        d = pd.to_datetime(text).date()
        for offset in (-1, 0, 1):
            q = d + timedelta(days=offset)
            if q.year == int(year) and q <= pd.to_datetime(cutoff_day).date():
                query_dates.add(q.strftime("%Y-%m-%d"))
    query_dates = sorted(query_dates, reverse=True)
    meta["query_dates"] = len(query_dates)

    all_rows = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(query_dates)))) as pool:
        futures = {pool.submit(_espn_day_events, day): day for day in query_dates}
        for future in as_completed(futures):
            try:
                rows, dm = future.result()
            except Exception as exc:
                rows, dm = [], {"error": str(exc)[:180]}
            if dm.get("error"):
                meta["scoreboard_errors"] += 1
            else:
                meta["scoreboard_ok"] += 1
            all_rows.extend(rows)

    target = int(wnba_team_id)
    cutoff = pd.to_datetime(cutoff_day).date()
    matched = []
    for row in all_rows:
        if target not in {int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)}:
            continue
        try:
            d = pd.to_datetime(row.get("date_utc"), utc=True).tz_convert(ET).date()
        except Exception:
            continue
        if d > cutoff:
            continue
        matched.append({
            "event_id": str(row.get("event_id") or ""),
            "date_utc": str(row.get("date_utc") or ""),
            "date_et": d.strftime("%Y-%m-%d"),
        })

    dedup = {r["event_id"]: r for r in matched if r.get("event_id")}
    rows = sorted(dedup.values(), key=lambda r: r["date_utc"], reverse=True)[:MAX_EVENTS_PER_TEAM]
    meta["events"] = len(rows)
    if not rows and not meta["error"]:
        meta["error"] = (
            f"official dates={len(official_dates)} but ESPN daily scoreboards produced "
            f"0 completed matching events (ok={meta['scoreboard_ok']}, errors={meta['scoreboard_errors']})"
        )
    return rows, meta


@st.cache_data(ttl=900, show_spinner=False, max_entries=16)
def _summary_history(year: int, team_ids: tuple[int, ...], cutoff_day: str, exclude_event_id: str = ""):
    fetched_at = datetime.now(ET).isoformat()
    clean_ids = tuple(sorted({int(x) for x in team_ids if int(x) > 0}))
    meta = {
        "fetched_at": fetched_at,
        "source": "WNBA official dates → ESPN daily scoreboard → ESPN summaries",
        "error": "",
        "games": 0,
        "candidate_events": 0,
        "summaries_ok": 0,
        "summary_errors": 0,
        "rejected": {},
        "team_schedule_errors": [],
        "team_discovery": [],
    }

    candidates = {}
    for team_id in clean_ids:
        events, tm = _team_schedule_events(team_id, int(year), cutoff_day)
        meta["team_discovery"].append(tm)
        if tm.get("error"):
            meta["team_schedule_errors"].append(str(tm.get("error")))
        for item in events:
            if str(item.get("event_id") or "") == str(exclude_event_id or ""):
                continue
            candidates[str(item["event_id"])] = item

    meta["candidate_events"] = len(candidates)
    if not candidates:
        parts = ["no historical ESPN event ids discovered from official WNBA dates"]
        if meta["team_schedule_errors"]:
            parts.append(" | ".join(meta["team_schedule_errors"])[:180])
        meta["error"] = " • ".join(parts)[:320]
        return [], meta

    parsed = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(candidates)))) as pool:
        futures = {pool.submit(old._summary, event_id): event_id for event_id in candidates}
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                payload, sm = future.result()
            except Exception as exc:
                payload, sm = {}, {"error": str(exc)[:180]}
            if sm.get("error"):
                meta["summary_errors"] += 1
                continue
            row, reason = old._parse_summary(payload, event_id)
            if row is None:
                meta["rejected"][reason] = int(meta["rejected"].get(reason, 0)) + 1
                continue
            if clean_ids and int(row.get("away_team_id") or 0) not in clean_ids and int(row.get("home_team_id") or 0) not in clean_ids:
                meta["rejected"]["NOT_TARGET_TEAM"] = int(meta["rejected"].get("NOT_TARGET_TEAM", 0)) + 1
                continue
            parsed.append(row)
            meta["summaries_ok"] += 1

    dedup = {}
    for row in parsed:
        key = str(row.get("event_id") or "") or f"{row.get('date_utc')}:{row.get('away_team_id')}:{row.get('home_team_id')}"
        dedup[key] = row
    rows = sorted(dedup.values(), key=lambda r: r["date_utc"], reverse=True)
    meta["games"] = len(rows)
    if not rows:
        meta["error"] = (
            f"{len(candidates)} candidate events found but zero usable Q1-Q4 summaries; "
            f"summary_errors={meta['summary_errors']} rejected={meta['rejected']}"
        )[:320]
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
    cutoff = game.get("captured_at") or datetime.now(ET).isoformat()
    return {
        "away": old.base.profile(away_id, rows, cutoff, "AWAY", event_id) if away_id else {},
        "home": old.base.profile(home_id, rows, cutoff, "HOME", event_id) if home_id else {},
        "meta": meta,
    }


def clear_cache():
    for fn in (_espn_day_events, _team_schedule_events, _summary_history):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        old._summary.clear()
    except Exception:
        pass


profile = old.base.profile
_reliability = old.base._reliability
