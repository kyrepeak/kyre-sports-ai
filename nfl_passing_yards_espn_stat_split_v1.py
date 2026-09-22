"""Verified ESPN season-stat transport for NFL Passing Yards.

ESPN Core season statistics expose the all-splits payload at ``statistics/0``.
The older Passing Yards loaders stopped at ``statistics``. That endpoint can be
inconsistent for athlete/team season data and was leaving opening-week cards
blank even though the verified prior-season statistics existed.

This transport requests the explicit all-splits resource first and keeps the
older collection/resource URL only as a compatibility fallback. Exact ESPN
athlete/team IDs remain mandatory. No sportsbook data is used.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_passing_yards_defense_v1 as defense
import nfl_passing_yards_profile_v1 as profile

MODEL_VERSION = "NFL PASSING YARDS ESPN STAT SPLIT TRANSPORT V1"


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _first_ok(urls: list[str], getter) -> tuple[dict, dict]:
    attempts: list[dict] = []
    last_payload: dict = {}
    last_diag: dict = {"ok": False, "http": None, "error": "no endpoint attempted"}
    for url in urls:
        payload, diag = getter(url)
        diag = dict(diag or {})
        attempts.append({
            "url": url,
            "http": diag.get("http"),
            "ok": bool(diag.get("ok")),
            "error": _safe(diag.get("error")),
        })
        last_payload = dict(payload or {}) if isinstance(payload, dict) else {}
        last_diag = diag
        if diag.get("ok") and isinstance(payload, dict):
            out_diag = dict(diag)
            out_diag["attempts"] = attempts
            out_diag["selected_url"] = url
            out_diag["split_zero"] = url.endswith("/0")
            return payload, out_diag
    out_diag = dict(last_diag)
    out_diag["attempts"] = attempts
    out_diag["selected_url"] = ""
    out_diag["split_zero"] = False
    return last_payload, out_diag


@st.cache_data(ttl=300, show_spinner=False)
def athlete_stats_payload(year: int, season_type: int, athlete_id: str):
    athlete_id = _safe(athlete_id)
    if not athlete_id or not athlete_id.isdigit():
        return {}, {"ok": False, "http": None, "error": "missing verified ESPN athlete id"}
    base = (
        f"{profile.CORE_BASE}/seasons/{int(year)}/types/{int(season_type)}"
        f"/athletes/{athlete_id}/statistics"
    )
    return _first_ok([f"{base}/0", base], profile._json_get)


@st.cache_data(ttl=300, show_spinner=False)
def team_stats_payload(year: int, season_type: int, team_id: str):
    team_id = _safe(team_id)
    if not team_id or not team_id.isdigit():
        return {}, {"ok": False, "http": None, "error": "missing verified ESPN team id"}
    base = (
        f"{defense.CORE_BASE}/seasons/{int(year)}/types/{int(season_type)}"
        f"/teams/{team_id}/statistics"
    )
    return _first_ok([f"{base}/0", base], defense._json_get)


__all__ = [
    "MODEL_VERSION",
    "athlete_stats_payload",
    "team_stats_payload",
]
