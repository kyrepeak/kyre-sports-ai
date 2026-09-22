"""WNBA Live Games Step-5 validation preview.

Isolated completed-game preview used only when no Step-1 verified game is live.
It reuses the proven ESPN daily-scoreboard + summary transports to let us verify
Step-5 H2H, starters, entered-player rotation and current availability rendering
without manufacturing a live state.

Nothing here is eligible for live markets, projection, probability, Monte Carlo,
edge, EV, qualification, ranking or recommendation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_availability_v33 as availability
import wnba_data_v232 as data232
import wnba_live_flow_v1 as flow
import wnba_live_second_half_v13 as hist13
import wnba_live_second_half_v14 as hist14

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE STEP-5 PREVIEW V1 • COMPLETED-GAME VALIDATION"
MAX_PREVIEWS = 8
LOOKBACK_DAYS = 21


def _safe_int(value, default=0):
    try:
        if isinstance(value, dict):
            value = value.get("value") or value.get("displayValue")
        return int(round(float(value)))
    except Exception:
        return int(default)


def _team_id(team: dict) -> int:
    try:
        return int(data232._team_id(team or {}) or 0)
    except Exception:
        try:
            return int((team or {}).get("id") or 0)
        except Exception:
            return 0


def _logo(team: dict) -> str:
    if not isinstance(team, dict):
        return ""
    if team.get("logo"):
        return str(team.get("logo"))
    logos = team.get("logos") or []
    if isinstance(logos, list):
        for item in logos:
            if isinstance(item, dict) and item.get("href"):
                return str(item.get("href"))
    return ""


def _competition(payload: dict) -> dict:
    header = (payload or {}).get("header") or {}
    comps = header.get("competitions") or []
    return comps[0] if comps and isinstance(comps[0], dict) else {}


def _preview_game(event_row: dict, payload: dict) -> dict | None:
    comp = _competition(payload)
    competitors = comp.get("competitors") or []
    sides = {
        str(c.get("homeAway") or "").lower(): c
        for c in competitors
        if isinstance(c, dict)
    }
    away = sides.get("away") or {}
    home = sides.get("home") or {}
    away_team = away.get("team") or {}
    home_team = home.get("team") or {}

    away_id = _team_id(away_team) or _safe_int(event_row.get("away_team_id"))
    home_id = _team_id(home_team) or _safe_int(event_row.get("home_team_id"))
    event_id = str(event_row.get("event_id") or "").strip()
    if not event_id or not away_id or not home_id:
        return None

    start = comp.get("date") or event_row.get("date_utc") or datetime.now(ET).isoformat()
    try:
        captured = pd.to_datetime(start, utc=True).isoformat()
        game_date_et = pd.to_datetime(start, utc=True).tz_convert(ET).strftime("%Y-%m-%d")
    except Exception:
        captured = datetime.now(ET).isoformat()
        game_date_et = str(event_row.get("date_et") or "")

    away_name = str(
        away_team.get("displayName")
        or away_team.get("shortDisplayName")
        or away_team.get("name")
        or f"Team {away_id}"
    )
    home_name = str(
        home_team.get("displayName")
        or home_team.get("shortDisplayName")
        or home_team.get("name")
        or f"Team {home_id}"
    )

    return {
        "espn_event_id": event_id,
        "event_id": event_id,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "away_team": away_name,
        "home_team": home_name,
        "away_abbr": str(away_team.get("abbreviation") or ""),
        "home_abbr": str(home_team.get("abbreviation") or ""),
        "away_logo": _logo(away_team),
        "home_logo": _logo(home_team),
        "away_score": _safe_int(away.get("score")),
        "home_score": _safe_int(home.get("score")),
        "phase": "FINAL • PREVIEW",
        "clock": "0:00",
        "period": 4,
        "captured_at": captured,
        "game_date_et": game_date_et,
        "preview_only": True,
    }


@st.cache_data(ttl=600, show_spinner=False, max_entries=4)
def recent_completed_previews(day_str: str, limit: int = MAX_PREVIEWS, lookback_days: int = LOOKBACK_DAYS):
    end_day = pd.to_datetime(day_str).date()
    previews = []
    meta = {
        "source": "ESPN WNBA daily scoreboard → ESPN event summary",
        "days_scanned": 0,
        "scoreboard_ok": 0,
        "scoreboard_errors": 0,
        "events_seen": 0,
        "summaries_ok": 0,
        "summary_errors": 0,
        "non_regular_rejected": 0,
        "usable": 0,
        "error": "",
    }

    for offset in range(max(1, int(lookback_days))):
        day = end_day - timedelta(days=offset)
        rows, dm = hist13._espn_day_events(day.strftime("%Y-%m-%d"))
        meta["days_scanned"] += 1
        if (dm or {}).get("error"):
            meta["scoreboard_errors"] += 1
            continue
        meta["scoreboard_ok"] += 1
        meta["events_seen"] += len(rows)

        rows = sorted(rows, key=lambda r: str(r.get("date_utc") or ""), reverse=True)
        for row in rows:
            event_id = str(row.get("event_id") or "")
            if not event_id:
                continue
            payload, sm = flow.espn_summary(event_id)
            if not payload:
                meta["summary_errors"] += 1
                continue
            meta["summaries_ok"] += 1

            try:
                regular = hist14._summary_regular(payload)
            except Exception:
                regular = None
            if regular is False:
                meta["non_regular_rejected"] += 1
                continue

            game = _preview_game(row, payload)
            if game is None:
                continue
            previews.append(game)
            if len(previews) >= int(limit):
                break
        if len(previews) >= int(limit):
            break

    dedup = {}
    for game in previews:
        event_id = str(game.get("espn_event_id") or "")
        if event_id:
            dedup[event_id] = game
    previews = sorted(
        dedup.values(),
        key=lambda g: str(g.get("captured_at") or ""),
        reverse=True,
    )[: int(limit)]
    meta["usable"] = len(previews)
    if not previews:
        meta["error"] = (
            f"no completed regular-season preview game found after {meta['days_scanned']} day(s); "
            f"scoreboard_ok={meta['scoreboard_ok']} scoreboard_errors={meta['scoreboard_errors']} "
            f"summaries_ok={meta['summaries_ok']}"
        )
    return previews, meta


def current_availability_for_preview(game: dict) -> dict:
    """Current team-feed availability only; never presented as historical injury state."""
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    day = datetime.now(ET).strftime("%Y-%m-%d")
    try:
        raw = availability.availability_for_game_key("", away_id, home_id, day)
    except Exception as exc:
        return {
            "injuries": [],
            "starters": [],
            "summary_connected": False,
            "team_feeds_connected": 0,
            "team_status_coverage": {away_id: False, home_id: False},
            "source": "ESPN WNBA current team injury feeds",
            "error": str(exc)[:220],
        }
    raw = dict(raw or {})
    raw["summary_connected"] = False
    raw["source"] = "ESPN WNBA current team injury feeds • preview-time snapshot"
    raw.setdefault("error", "")
    return raw


def clear_cache():
    try:
        recent_completed_previews.clear()
    except Exception:
        pass
    try:
        flow.clear_cache()
    except Exception:
        pass
    try:
        availability.clear_availability_cache()
    except Exception:
        pass
