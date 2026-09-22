"""Kyre Sports AI — NFL Moneyline V4.1 Step-4A historical data repair.

Repairs V4.0's historical baseline retrieval without changing the Step-4A model
formula or minimum-data guard. The existing ESPN team-schedule path remains
primary. When it returns insufficient usable regular-season games, V4.1 rebuilds
that season from ESPN's league scoreboard week-by-week and filters the requested
team from completed regular-season events.

No preseason result is used in team strength. No sportsbook price, calibrated
P(win), Monte Carlo, EV, ranking or recommendation logic is enabled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v4 as v4

MODEL_VERSION = "NFL MONEYLINE V4.1 • STEP 4A HISTORICAL FALLBACK REPAIR"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
HEADERS = v4.HEADERS
REGULAR_WEEKS = tuple(range(1, 19))


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _num(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def _score(comp: dict):
    value = (comp or {}).get("score")
    if isinstance(value, dict):
        value = value.get("value") or value.get("displayValue")
    return _num(value)


@st.cache_data(ttl=21600, show_spinner=False)
def _league_regular_season_games(season: int):
    """Reconstruct one NFL regular season from ESPN scoreboard weeks 1-18."""
    rows = []
    diagnostics = {
        "ok": False,
        "season": int(season),
        "weeks_ok": 0,
        "weeks_attempted": len(REGULAR_WEEKS),
        "events": 0,
        "error": "",
        "provider": "ESPN NFL league scoreboard weekly fallback",
    }

    for week in REGULAR_WEEKS:
        params = {
            "dates": str(int(season)),
            "seasontype": 2,
            "week": int(week),
            "limit": 100,
        }
        try:
            r = requests.get(ESPN_SCOREBOARD, params=params, headers=HEADERS, timeout=8)
            r.raise_for_status()
            payload = r.json()
            diagnostics["weeks_ok"] += 1
        except Exception as exc:
            if not diagnostics["error"]:
                diagnostics["error"] = str(exc)[:220]
            continue

        for event in payload.get("events", []) or []:
            season_obj = event.get("season") or {}
            try:
                season_type = int(season_obj.get("type") or 0)
            except Exception:
                season_type = 0
            if season_type and season_type != 2:
                continue

            status = (event.get("status") or {}).get("type") or {}
            if not bool(status.get("completed")) and _safe(status.get("state")).lower() != "post":
                continue

            try:
                event_ts = pd.to_datetime(event.get("date"), utc=True).tz_convert(foundation.ET)
            except Exception:
                continue

            comps = event.get("competitions") or []
            if not comps:
                continue
            competitors = comps[0].get("competitors") or []
            if len(competitors) < 2:
                continue

            parsed = []
            for comp in competitors:
                team = comp.get("team") or {}
                abbr = _safe(team.get("abbreviation")).upper()
                score = _score(comp)
                if not abbr or not np.isfinite(score):
                    continue
                parsed.append({
                    "abbr": abbr,
                    "team": _safe(team.get("displayName") or team.get("shortDisplayName"), abbr),
                    "score": float(score),
                    "home_away": _safe(comp.get("homeAway")).lower(),
                })
            if len(parsed) != 2:
                continue

            diagnostics["events"] += 1
            for ours, opp in ((parsed[0], parsed[1]), (parsed[1], parsed[0])):
                pf, pa = ours["score"], opp["score"]
                rows.append({
                    "season": int(season),
                    "week": int(week),
                    "game_id": _safe(event.get("id")),
                    "date": event_ts,
                    "team_abbr": ours["abbr"],
                    "team": ours["team"],
                    "result": "T" if pf == pa else ("W" if pf > pa else "L"),
                    "pf": pf,
                    "pa": pa,
                    "margin": pf - pa,
                    "opponent": opp["team"],
                    "opponent_abbr": opp["abbr"],
                    "home_away": ours["home_away"],
                })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = (
            frame.sort_values(["date", "game_id"])
            .drop_duplicates(subset=["game_id", "team_abbr"], keep="last")
            .reset_index(drop=True)
        )
    diagnostics["ok"] = bool(diagnostics["weeks_ok"] >= 12 and not frame.empty)
    return frame, diagnostics


_ORIGINAL_COMPLETED = v4._completed_regular_games


def _completed_regular_games(team_abbr: str, season: int, cutoff_day: str):
    """Primary team schedule, then verified league-wide fallback when needed."""
    primary, pdiag = _ORIGINAL_COMPLETED(team_abbr, season, cutoff_day)
    primary_count = int(len(primary)) if primary is not None else 0

    # A full prior regular season should normally contain 17 games. Keep the
    # original path when it has a meaningful sample; current-season partial data
    # also remains valid and does not need fallback simply because it is early.
    cutoff = pd.to_datetime(cutoff_day).date()
    season_end_boundary = pd.Timestamp(f"{int(season)+1}-03-01").date()
    historical_full_season_request = cutoff >= pd.Timestamp(f"{int(season)}-12-01").date()

    if pdiag.get("ok") and (primary_count >= 12 or not historical_full_season_request):
        pdiag = dict(pdiag)
        pdiag["path"] = "TEAM SCHEDULE PRIMARY"
        return primary, pdiag

    league, ldiag = _league_regular_season_games(int(season))
    if ldiag.get("ok") and not league.empty:
        abbr = _safe(team_abbr).upper()
        team = league[league["team_abbr"].astype(str).str.upper() == abbr].copy()
        if not team.empty:
            cutoff_ts = pd.Timestamp(cutoff)
            if team["date"].dt.tz is not None:
                cutoff_ts = cutoff_ts.tz_localize(foundation.ET)
            team = team[team["date"] < cutoff_ts + pd.Timedelta(days=1)].copy()
            if not team.empty:
                out = team[["date", "result", "pf", "pa", "margin", "opponent", "opponent_abbr", "home_away"]].copy()
                out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
                out = out.sort_values("date").drop_duplicates(subset=["date", "opponent_abbr"], keep="last").reset_index(drop=True)
                diag = {
                    "ok": True,
                    "http": pdiag.get("http"),
                    "error": "",
                    "team": abbr,
                    "season": int(season),
                    "games": int(len(out)),
                    "provider": "ESPN NFL league scoreboard fallback",
                    "path": "LEAGUE WEEKLY FALLBACK",
                    "primary_games": primary_count,
                    "weeks_ok": ldiag.get("weeks_ok"),
                }
                return out, diag

    pdiag = dict(pdiag)
    pdiag["path"] = "TEAM SCHEDULE PRIMARY • FALLBACK FAILED"
    pdiag["fallback_weeks_ok"] = ldiag.get("weeks_ok")
    pdiag["fallback_error"] = ldiag.get("error")
    return primary, pdiag


# Patch V4's profile builder at the retrieval seam; index math remains unchanged.
v4._completed_regular_games = _completed_regular_games


def render_nfl_moneyline_hub():
    return v4.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
