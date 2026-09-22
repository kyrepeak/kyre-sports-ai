"""WNBA Live Step 4 history transport V1.4.

Root-cause repair: historical discovery no longer depends on either the WNBA CDN
(which is returning non-JSON on Streamlit) or ESPN team schedules (which returned
zero historical event ids). We scan ESPN's proven date-specific WNBA scoreboard
backward in small chunks, then use ESPN summaries for Q1-Q4 linescores.

Read-only descriptive layer. No sportsbook input, projection, probability,
Monte Carlo, edge, EV, qualification or pick is created here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_second_half_v13 as prev

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE SECOND-HALF HISTORY V1.4 • ESPN ROLLING-DATE BACKFILL"
MAX_EVENTS_PER_TEAM = 20
CHUNK_DAYS = 14
MAX_WORKERS = 8
SEASON_FLOOR_MONTH = 4
SEASON_FLOOR_DAY = 1


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


@st.cache_data(ttl=900, show_spinner=False, max_entries=16)
def _discover(year: int, team_ids: tuple[int, ...], cutoff_day: str):
    targets = tuple(sorted({int(x) for x in team_ids if int(x) > 0}))
    cutoff = pd.to_datetime(cutoff_day).date()
    floor = date(int(year), SEASON_FLOOR_MONTH, SEASON_FLOOR_DAY)
    cursor = cutoff - timedelta(days=1)

    meta = {
        "source": "ESPN daily scoreboard rolling-date scan",
        "days_scanned": 0,
        "oldest_day_scanned": "",
        "scoreboard_ok": 0,
        "scoreboard_errors": 0,
        "matched_events": 0,
        "per_team_found": {str(t): 0 for t in targets},
        "error": "",
    }
    if not targets:
        meta["error"] = "no valid WNBA target team ids"
        return [], meta

    found = {}
    while cursor >= floor:
        days = []
        for _ in range(CHUNK_DAYS):
            if cursor < floor:
                break
            days.append(cursor.strftime("%Y-%m-%d"))
            cursor -= timedelta(days=1)
        if not days:
            break

        meta["days_scanned"] += len(days)
        meta["oldest_day_scanned"] = days[-1]

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(days))) as pool:
            futures = {pool.submit(prev._espn_day_events, day): day for day in days}
            for future in as_completed(futures):
                try:
                    rows, dm = future.result()
                except Exception as exc:
                    rows, dm = [], {"error": str(exc)[:180]}
                if dm.get("error"):
                    meta["scoreboard_errors"] += 1
                else:
                    meta["scoreboard_ok"] += 1
                for row in rows:
                    away_id = int(row.get("away_team_id") or 0)
                    home_id = int(row.get("home_team_id") or 0)
                    if any(t in {away_id, home_id} for t in targets):
                        event_id = str(row.get("event_id") or "")
                        if event_id:
                            found[event_id] = row

        counts = {}
        for target in targets:
            rows_for_team = [
                row for row in found.values()
                if target in {
                    int(row.get("away_team_id") or 0),
                    int(row.get("home_team_id") or 0),
                }
            ]
            counts[target] = len(rows_for_team)
            meta["per_team_found"][str(target)] = len(rows_for_team)

        if all(counts.get(t, 0) >= MAX_EVENTS_PER_TEAM for t in targets):
            break

    ordered = sorted(found.values(), key=lambda r: r.get("date_utc") or "", reverse=True)
    selected = {}
    for target in targets:
        rows_for_team = [
            row for row in ordered
            if target in {
                int(row.get("away_team_id") or 0),
                int(row.get("home_team_id") or 0),
            }
        ][:MAX_EVENTS_PER_TEAM]
        for row in rows_for_team:
            selected[str(row["event_id"])] = row

    rows = sorted(selected.values(), key=lambda r: r.get("date_utc") or "", reverse=True)
    meta["matched_events"] = len(rows)
    if not rows:
        meta["error"] = (
            f"rolling ESPN daily scan found no completed target-team games after "
            f"{meta['days_scanned']} day(s); scoreboard_ok={meta['scoreboard_ok']} "
            f"errors={meta['scoreboard_errors']}"
        )[:320]
    return rows, meta


def _summary_regular(payload: dict):
    try:
        header, comp = prev.old._summary_comp(payload)
        return prev.old.base._regular_season_flag(header, comp)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=16)
def _history(year: int, team_ids: tuple[int, ...], cutoff_day: str, exclude_event_id: str = ""):
    candidates, scan = _discover(int(year), team_ids, cutoff_day)
    candidates = [
        row for row in candidates
        if str(row.get("event_id") or "") != str(exclude_event_id or "")
    ]
    meta = {
        "fetched_at": datetime.now(ET).isoformat(),
        "source": "ESPN rolling daily scoreboards → ESPN event summaries",
        "candidate_events": len(candidates),
        "summaries_ok": 0,
        "summary_errors": 0,
        "games": 0,
        "rejected": {},
        "scan": scan,
        "error": "",
    }
    if not candidates:
        meta["error"] = scan.get("error") or "no completed historical ESPN event ids discovered"
        return [], meta

    parsed = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(candidates))) as pool:
        futures = {
            pool.submit(prev.old._summary, str(row["event_id"])): str(row["event_id"])
            for row in candidates
        }
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                payload, sm = future.result()
            except Exception as exc:
                payload, sm = {}, {"error": str(exc)[:180]}
            if sm.get("error"):
                meta["summary_errors"] += 1
                continue
            if _summary_regular(payload) is False:
                meta["rejected"]["NON_REGULAR"] = int(meta["rejected"].get("NON_REGULAR", 0)) + 1
                continue

            row, reason = prev.old._parse_summary(payload, event_id)
            if row is None:
                meta["rejected"][reason] = int(meta["rejected"].get(reason, 0)) + 1
                continue
            parsed.append(row)
            meta["summaries_ok"] += 1

    dedup = {
        str(row.get("event_id") or f"{row.get('date_utc')}:{row.get('away_team_id')}:{row.get('home_team_id')}"): row
        for row in parsed
    }
    rows = sorted(dedup.values(), key=lambda r: r["date_utc"], reverse=True)
    meta["games"] = len(rows)
    if not rows:
        meta["error"] = (
            f"{len(candidates)} candidate event(s) found, but zero usable Q1-Q4 summaries; "
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

    rows, meta = _history(year, team_ids, cutoff_day, event_id)
    cutoff = game.get("captured_at") or datetime.now(ET).isoformat()
    return {
        "away": prev.old.base.profile(away_id, rows, cutoff, "AWAY", event_id) if away_id else {},
        "home": prev.old.base.profile(home_id, rows, cutoff, "HOME", event_id) if home_id else {},
        "meta": meta,
    }


def clear_cache():
    for fn in (_discover, _history):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        prev._espn_day_events.clear()
    except Exception:
        pass
    try:
        prev.old._summary.clear()
    except Exception:
        pass


profile = prev.old.base.profile
_reliability = prev.old.base._reliability
