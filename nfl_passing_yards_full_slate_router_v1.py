"""Passing Yards full-slate schedule router.

The frozen daily ESPN slate remains primary. nflverse is used only as an
independent completeness contract (expected game count/week). When the daily
ESPN response is incomplete, the router asks ESPN's official week scoreboard
for the same season/week, filters back to the selected ET date, and unions the
official ESPN event rows by game_id.

No game identity is synthesized and nflverse rows never become app game rows.
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import requests

import nfl_hub_v1 as base
from sports_api import nfl_data_nflverse_v1 as nflverse

PRIMARY_SOURCE = "ESPN NFL scoreboard daily"
FALLBACK_SOURCE = "ESPN NFL scoreboard week"
COMPLETENESS_SOURCE = "nflverse games.csv"
REQUEST_TIMEOUT_SECONDS = 10

SlateLoader = Callable[[str], tuple[pd.DataFrame, dict[str, Any]]]
ScheduleLoader = Callable[[str], dict[str, Any]]
WeeklyLoader = Callable[[str, dict[str, Any]], tuple[pd.DataFrame, dict[str, Any]]]


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _season_type_from_game_type(value: Any) -> int:
    game_type = _safe(value).upper()
    if game_type == "PRE":
        return 1
    if game_type == "REG":
        return 2
    if game_type in {"WC", "DIV", "CON", "SB", "POST"}:
        return 3
    return 0


def _default_schedule_meta(day_str: str) -> dict[str, Any]:
    frame = nflverse._load_games_csv()
    if frame is None or getattr(frame, "empty", True):
        return {"ready": False, "expected_games": 0}
    required = {"gameday", "season", "week", "game_type"}
    if not required.issubset(frame.columns):
        return {"ready": False, "expected_games": 0}

    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    rows = frame[frame["gameday"].astype(str).str[:10].eq(day)].copy()
    if rows.empty:
        return {"ready": False, "expected_games": 0}

    season_values = pd.to_numeric(rows["season"], errors="coerce").dropna()
    week_values = pd.to_numeric(rows["week"], errors="coerce").dropna()
    game_types = [str(v) for v in rows["game_type"].dropna().tolist()]
    if season_values.empty or week_values.empty or not game_types:
        return {"ready": False, "expected_games": int(len(rows))}

    season = int(season_values.mode().iloc[0])
    week = int(week_values.mode().iloc[0])
    season_type = _season_type_from_game_type(pd.Series(game_types).mode().iloc[0])
    if season_type <= 0:
        return {"ready": False, "expected_games": int(len(rows))}

    return {
        "ready": True,
        "expected_games": int(len(rows)),
        "season": season,
        "week": week,
        "season_type": season_type,
        "source": COMPLETENESS_SOURCE,
    }


def _parse_scoreboard_payload(payload: dict[str, Any], day_str: str) -> pd.DataFrame:
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    rows: list[dict[str, Any]] = []
    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        competition = comps[0]
        sides: dict[str, dict[str, Any]] = {}
        for competitor in competition.get("competitors", []) or []:
            sides[base._safe_text(competitor.get("homeAway")).lower()] = competitor
        away = sides.get("away") or {}
        home = sides.get("home") or {}
        away_team = away.get("team") or {}
        home_team = home.get("team") or {}
        away_abbr = base._safe_text(away_team.get("abbreviation"), "AWY").upper()
        home_abbr = base._safe_text(home_team.get("abbreviation"), "HME").upper()
        status_type = (event.get("status") or {}).get("type") or {}
        state = base._safe_text(status_type.get("state"), "pre").lower()
        detail = base._safe_text(
            status_type.get("shortDetail")
            or status_type.get("detail")
            or status_type.get("description"),
            "Scheduled",
        )
        tip, event_day = base._tip_et(event.get("date") or competition.get("date"))
        if event_day and event_day != day:
            continue
        venue = competition.get("venue") or {}
        address = venue.get("address") or {}
        broadcasts: list[str] = []
        for block in competition.get("broadcasts", []) or []:
            for name in block.get("names", []) or []:
                if name and name not in broadcasts:
                    broadcasts.append(str(name))
        season = event.get("season") or {}
        rows.append(
            {
                "game_id": base._safe_text(event.get("id")),
                "game_date": event_day or day,
                "tip_et": tip,
                "state": state,
                "status": detail,
                "season_type": base._season_label(season.get("type")),
                "away_team": base._safe_text(
                    away_team.get("displayName") or away_team.get("shortDisplayName"),
                    "Away",
                ),
                "away_abbr": away_abbr,
                "away_logo": base._logo(away_team, away_abbr),
                "away_record": base._record(away),
                "away_score": base._safe_text(away.get("score")),
                "home_team": base._safe_text(
                    home_team.get("displayName") or home_team.get("shortDisplayName"),
                    "Home",
                ),
                "home_abbr": home_abbr,
                "home_logo": base._logo(home_team, home_abbr),
                "home_record": base._record(home),
                "home_score": base._safe_text(home.get("score")),
                "venue": base._safe_text(venue.get("fullName"), "Venue TBD"),
                "location": ", ".join(
                    x
                    for x in (
                        base._safe_text(address.get("city")),
                        base._safe_text(address.get("state")),
                    )
                    if x
                ),
                "broadcast": " / ".join(broadcasts) if broadcasts else "—",
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["game_id"], keep="first").reset_index(drop=True)
    return frame


def _default_weekly_loader(
    day_str: str,
    meta: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    params = {
        "dates": str(int(meta["season"])),
        "seasontype": int(meta["season_type"]),
        "week": int(meta["week"]),
        "limit": 100,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
    }
    diag = {
        "provider": FALLBACK_SOURCE,
        "http": None,
        "request_ok": False,
        "games": 0,
        "error": "",
    }
    try:
        response = requests.get(
            base.ESPN_SCOREBOARD,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        diag["http"] = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
        frame = _parse_scoreboard_payload(payload, day_str)
    except Exception as exc:
        diag["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
        return pd.DataFrame(), diag

    diag["request_ok"] = True
    diag["games"] = int(len(frame))
    return frame, diag


def load_full_slate(
    day_str: str,
    *,
    primary_loader: SlateLoader,
    schedule_loader: ScheduleLoader | None = None,
    weekly_loader: WeeklyLoader | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return the fullest exact-ID ESPN slate for one ET calendar date."""
    primary, primary_diag = primary_loader(day_str)
    primary = primary.copy() if isinstance(primary, pd.DataFrame) else pd.DataFrame()
    primary_diag = dict(primary_diag or {})

    schedule = (schedule_loader or _default_schedule_meta)(day_str)
    expected = int(schedule.get("expected_games") or 0)
    if (
        not schedule.get("ready")
        or expected <= 0
        or (primary_diag.get("request_ok") and len(primary) >= expected)
    ):
        out_diag = dict(primary_diag)
        out_diag.update(
            {
                "full_slate_router": True,
                "fallback_used": False,
                "expected_games": expected,
                "games": int(len(primary)),
            }
        )
        return primary, out_diag

    weekly, weekly_diag = (weekly_loader or _default_weekly_loader)(day_str, schedule)
    if weekly_diag.get("request_ok") and not weekly.empty:
        combined = pd.concat([primary, weekly], ignore_index=True)
        if "game_id" in combined.columns:
            combined = combined.drop_duplicates(subset=["game_id"], keep="first")
        combined = combined.reset_index(drop=True)
    else:
        combined = primary

    fallback_helped = len(combined) > len(primary)
    out_diag = dict(primary_diag)
    out_diag.update(
        {
            "provider": (
                f"{PRIMARY_SOURCE} + {FALLBACK_SOURCE}"
                if fallback_helped
                else primary_diag.get("provider", PRIMARY_SOURCE)
            ),
            "request_ok": bool(primary_diag.get("request_ok") or weekly_diag.get("request_ok")),
            "full_slate_router": True,
            "fallback_used": fallback_helped,
            "expected_games": expected,
            "primary_games": int(len(primary)),
            "weekly_games": int(len(weekly)),
            "games": int(len(combined)),
            "weekly_http": weekly_diag.get("http"),
        }
    )
    return combined, out_diag


__all__ = [
    "COMPLETENESS_SOURCE",
    "FALLBACK_SOURCE",
    "PRIMARY_SOURCE",
    "load_full_slate",
]
