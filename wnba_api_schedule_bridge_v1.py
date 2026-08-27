"""Step 7F — API-first compatibility bridge for Streamlit WNBA schedule reads.

The existing Streamlit WNBA modules import ``wnba_schedule_v25``.  This bridge
replaces only its schedule transport functions at runtime.  The returned frame
keeps the historical V2.5 column contract, so projection/model code does not
change.  If the hosted Kyre Sports API is unavailable or returns an invalid
payload, the exact pre-Step-7F V2.5 functions are used as a fail-safe fallback.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import pandas as pd

from wnba_api_client_v1 import KyreWNBAAPIClient, KyreWNBAAPIError, SUPPORTED_SEASON

MODEL_VERSION = "WNBA STREAMLIT API SCHEDULE BRIDGE V1"
API_SOURCE_LABEL = "Kyre Sports API • WNBA official schedule"


class WNBAAPIScheduleBridgeError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status_label(game: Mapping[str, Any]) -> str:
    status = game.get("status") if isinstance(game.get("status"), Mapping) else {}
    category = _text(status.get("category")).upper()
    if category:
        return category
    text = _text(status.get("text"))
    return text.upper() if text else "UNKNOWN"


def _tip_label(game: Mapping[str, Any]) -> str:
    value = _text(game.get("game_datetime_eastern"))
    if not value:
        return "TBD"
    try:
        stamp = pd.to_datetime(value)
        return stamp.strftime("%-I:%M %p ET")
    except Exception:
        return value


def _team_name(team: Mapping[str, Any]) -> str:
    full = _text(team.get("full_name"))
    if full:
        return full
    city = _text(team.get("team_city"))
    name = _text(team.get("team_name"))
    return " ".join(part for part in (city, name) if part).strip()


def _venue(game: Mapping[str, Any]) -> str:
    venue = game.get("venue") if isinstance(game.get("venue"), Mapping) else {}
    name = _text(venue.get("name"))
    city = _text(venue.get("city"))
    if name:
        return name
    if city:
        return city
    return "Venue TBD"


def api_schedule_frame(payload: Mapping[str, Any], day_str: str, schedule_module) -> pd.DataFrame:
    if not isinstance(payload, Mapping):
        raise WNBAAPIScheduleBridgeError("Hosted schedule payload is not an object.")
    if int(payload.get("season") or 0) != SUPPORTED_SEASON:
        raise WNBAAPIScheduleBridgeError("Hosted schedule payload has the wrong season.")
    games = payload.get("games")
    if not isinstance(games, list):
        raise WNBAAPIScheduleBridgeError("Hosted schedule payload has no games list.")

    rows: list[dict[str, Any]] = []
    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        away = raw.get("away") if isinstance(raw.get("away"), Mapping) else {}
        home = raw.get("home") if isinstance(raw.get("home"), Mapping) else {}
        gid = _text(raw.get("game_id"))
        away_id = away.get("official_team_id")
        home_id = home.get("official_team_id")
        if not gid or away_id in (None, "") or home_id in (None, ""):
            continue
        rows.append({
            "game_id": gid,
            "game_date": _text(raw.get("official_schedule_date")) or str(day_str),
            "first_tip_et": _tip_label(raw),
            "status": _status_label(raw),
            "status_text": _text((raw.get("status") or {}).get("text")) if isinstance(raw.get("status"), Mapping) else "",
            "away_team_id": int(away_id),
            "away_team": _team_name(away),
            "away_tricode": _text(away.get("team_tricode")),
            "home_team_id": int(home_id),
            "home_team": _team_name(home),
            "home_tricode": _text(home.get("team_tricode")),
            "venue": _venue(raw),
            "source": API_SOURCE_LABEL,
        })

    if not rows:
        frame = schedule_module._empty_schedule()
    else:
        frame = pd.DataFrame(rows)
        frame = schedule_module.v24.guarded._guard_schedule(frame).reset_index(drop=True)
    return frame


def install_wnba_api_schedule_bridge(*, client: KyreWNBAAPIClient | None = None) -> dict[str, Any]:
    """Patch WNBA schedule V2.5 in-place and return sanitized installation evidence."""
    import wnba_schedule_v25 as schedule25

    if getattr(schedule25, "_kyre_step7f_api_bridge_installed", False):
        return {
            "installed": True,
            "already_installed": True,
            "model_version": MODEL_VERSION,
            "api_base_url": (client or KyreWNBAAPIClient()).base_url,
        }

    api = client or KyreWNBAAPIClient()
    original_schedule = schedule25.schedule_for_date
    original_diagnostics = schedule25.schedule_diagnostics
    setattr(schedule25, "_kyre_step7f_original_schedule_for_date", original_schedule)
    setattr(schedule25, "_kyre_step7f_original_schedule_diagnostics", original_diagnostics)

    def schedule_for_date_api_first(day: str | date):
        day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
        try:
            payload = api.games_for_date(day_str, SUPPORTED_SEASON)
            return api_schedule_frame(payload, day_str, schedule25)
        except Exception:
            return original_schedule(day)

    def schedule_diagnostics_api_first(day: str | date):
        day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
        try:
            payload = api.games_for_date(day_str, SUPPORTED_SEASON)
            frame = api_schedule_frame(payload, day_str, schedule25)
            return {
                "selected_date": day_str,
                "state": "VERIFIED_API" if len(frame) else "VERIFIED_API_OFF_DAY",
                "games": int(len(frame)),
                "teams": int(len(set(frame.get("away_team_id", pd.Series(dtype=int)).tolist() + frame.get("home_team_id", pd.Series(dtype=int)).tolist()))) if len(frame) else 0,
                "chosen_source": API_SOURCE_LABEL,
                "confirming_sources": ["Kyre Sports API"],
                "season_sources_ok": 1,
                "attempts": [{
                    "provider": "Kyre Sports API",
                    "status": "ok",
                    "selected_games": int(len(frame)),
                    "source_variant": payload.get("source_variant"),
                    "source_url": payload.get("source_url"),
                }],
                "source_selected_counts": {"Kyre Sports API": int(len(frame))},
                "rejected_single_source_matchups": 0,
                "timezone_rule": "America/New_York slate date",
                "step7f_api_first": True,
                "fallback_used": False,
            }
        except Exception as exc:
            legacy = original_diagnostics(day)
            result = dict(legacy or {})
            result.update({
                "step7f_api_first": True,
                "fallback_used": True,
                "api_error_type": type(exc).__name__,
            })
            return result

    schedule25.schedule_for_date = schedule_for_date_api_first
    schedule25.schedule_diagnostics = schedule_diagnostics_api_first
    schedule25._kyre_step7f_api_bridge_installed = True
    schedule25._kyre_step7f_api_client = api

    return {
        "installed": True,
        "already_installed": False,
        "model_version": MODEL_VERSION,
        "api_base_url": api.base_url,
        "patched_functions": ["schedule_for_date", "schedule_diagnostics"],
        "legacy_fallback_preserved": True,
        "sportsbook_transport_changed": False,
        "projection_math_changed": False,
        "monte_carlo_changed": False,
    }


__all__ = [
    "MODEL_VERSION",
    "API_SOURCE_LABEL",
    "WNBAAPIScheduleBridgeError",
    "api_schedule_frame",
    "install_wnba_api_schedule_bridge",
]
