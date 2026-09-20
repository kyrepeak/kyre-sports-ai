"""Game Evidence V2 — Step 6 runtime-fresh deterministic cache handoff.

Fresh module name guarantees the checked-in exact-event environment cache is
read in the deployed runtime before the frozen V1 adapter can attempt network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import cfb_game_total_game_evidence_v1 as prior

MODEL_VERSION = "CFB GAME TOTAL GAME EVIDENCE V2 • STEP 6 RUNTIME FRESH"
ENVIRONMENT_CACHE_PATH = Path(__file__).resolve().parent / "data" / "cfb_game_total_environment_cache_v1.json"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _cached_row(game: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _clean(game.get("espn_event_id") or game.get("event_id"))
    if not event_id:
        return {}
    try:
        payload = json.loads(ENVIRONMENT_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    row = (payload.get("events") or {}).get(event_id)
    if not isinstance(row, Mapping):
        return {}
    day = _clean(game.get("game_date") or game.get("date"))[:10]
    if day and _clean(row.get("game_date"))[:10] != day:
        return {}
    for key in ("away_team", "home_team"):
        expected = _clean(game.get(key)).casefold()
        actual = _clean(row.get(key)).casefold()
        if expected and actual and expected != actual:
            return {}
    return dict(row)


def _overlay_cached_environment(
    display_game: Mapping[str, Any],
    source_game: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    out = dict(display_game or {})
    row = _cached_row(source_game)
    if not row:
        return out, False

    venue = row.get("venue") if isinstance(row.get("venue"), Mapping) else {}
    weather = row.get("weather") if isinstance(row.get("weather"), Mapping) else {}
    if venue.get("ready") is not True or weather.get("ready") is not True:
        return out, False

    out["venue"] = _clean(venue.get("name")) or out.get("venue")
    city = _clean(venue.get("city"))
    state = _clean(venue.get("state"))
    if city or state:
        out["venue_location"] = ", ".join(x for x in (city, state) if x)
    out["temperature"] = weather.get("temperature_f")
    out["wind_mph"] = weather.get("gust_mph")
    if weather.get("gust_mph") is not None:
        out["wind"] = f"{float(weather['gust_mph']):.0f} mph gusts"
    if weather.get("precipitation_pct") is not None:
        out["weather"] = f"{float(weather['precipitation_pct']):.0f}% precipitation"
    if _clean(row.get("kickoff")):
        out["kickoff_iso"] = _clean(row.get("kickoff"))
    if _clean(row.get("status")):
        out["status"] = _clean(row.get("status"))
    out["weather_source"] = _clean(weather.get("source")) or "checked-in verified environment cache"
    out["game_evidence_event_id"] = _clean(row.get("event_id"))
    out["game_evidence_runtime_fresh_v2"] = True
    return out, True


def enrich_game_evidence(
    display_game: Mapping[str, Any],
    source_game: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = dict(source_game or display_game or {})
    overlaid, cache_used = _overlay_cached_environment(display_game, source)
    result, diag = prior.enrich_game_evidence(overlaid, source)
    out_diag = dict(diag or {})
    if cache_used:
        out_diag["source"] = "checked-in-verified-environment-cache-v1-via-v2"
        out_diag["cache_used"] = True
        out_diag["fallback_used"] = True
    out_diag["version_v2"] = MODEL_VERSION
    return result, out_diag


__all__ = [
    "ENVIRONMENT_CACHE_PATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_game_evidence",
]
