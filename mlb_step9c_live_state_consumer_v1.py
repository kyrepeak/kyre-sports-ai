"""Step 9C API-first live-state transport bridge for the frozen MLB V19.3 page.

This module changes transport only. The existing verified/direct MLB slate remains
untouched because it owns team IDs, probable pitchers, venue and other metadata
that are outside the Step 9A live-state contract. For the selected exact gamePk,
the bridge tries the hosted Step 9B live-state endpoint, validates the response
through the frozen Step 9A contract, and maps that certified state into the exact
V19 state dictionary. Any API, freshness, schema, identity or mapping failure
falls back to the original V18.2 live-feed function.
"""
from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime
import json
import os
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sports_api.mlb_step9a_live_game_state_api_contract_v1 import (
    DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    build_live_game_state_api_state,
    enforce_live_game_state_api_freshness,
    live_game_state_for_official_game_id,
)

DATA_TYPE = "mlb_step9c_live_state_consumer_v1"
SCHEMA_VERSION = 1
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
DEFAULT_TIMEOUT_SECONDS = 8.0
TAG = "__mlb_step9c_certified_live_state__"
MATCH_METHOD = "official_mlb_game_id_exact"

PROTECTED_FALSE_FLAGS = (
    "model_math_impact",
    "projection_impact",
    "simulation_math_impact",
    "probability_math_impact",
    "run_expectancy_math_impact",
    "ranking_impact",
    "selection_impact",
    "sportsbook_price_model_input",
    "team_name_matching_used",
    "player_name_matching_used",
    "fuzzy_matching_used",
    "synthetic_game_id_used",
    "durable_persistence",
    "wnba_impact",
)

_CURRENT_GAME: ContextVar[dict[str, Any] | None] = ContextVar(
    "mlb_step9c_current_game", default=None
)
_LAST_STATUS: dict[str, Any] = {
    "data_type": DATA_TYPE,
    "schema_version": SCHEMA_VERSION,
    "installed": False,
    "api_attempted": False,
    "api_used": False,
    "legacy_fallback_used": False,
    "official_game_id": None,
    "failure": None,
    **{key: False for key in PROTECTED_FALSE_FLAGS},
}


def _strict_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text and text.isascii() and text.isdecimal():
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def _safe_nonnegative_int(value: Any) -> int:
    parsed = _strict_positive_int(value)
    if parsed is not None:
        return parsed
    if value == 0 or value == "0":
        return 0
    return 0


def _base_url() -> str:
    value = str(os.getenv("KYRE_SPORTS_API_BASE_URL") or DEFAULT_API_BASE_URL).strip()
    return value.rstrip("/")


def _api_payload(
    official_game_id: int,
    *,
    game_date: str | None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "official_game_id": official_game_id,
        "max_games": 30,
    }
    if str(game_date or "").strip():
        params["date"] = str(game_date).strip()
    url = f"{_base_url()}/api/v1/mlb/live-game-state?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "KyreSportsMLBStep9CConsumer/1.0",
        },
        method="GET",
    )
    with urlopen(request, timeout=float(timeout)) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise RuntimeError(f"live-state API returned HTTP {status}")
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise RuntimeError("live-state API response exceeded 5 MB")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("live-state API did not return a JSON object")
    return payload


def _certified_context(
    official_game_id: int,
    *,
    game_date: str | None,
    payload_getter=None,
) -> dict[str, Any] | None:
    getter = payload_getter or _api_payload
    payload = getter(official_game_id, game_date=game_date)
    state = build_live_game_state_api_state(payload)
    state = enforce_live_game_state_api_freshness(
        state,
        max_age_seconds=DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    )
    return live_game_state_for_official_game_id(
        state,
        official_game_id=official_game_id,
    )


def _occupied_name(name: Any, runner_id: Any) -> str:
    text = str(name or "").strip()
    if text:
        return text
    return "Occupied" if _strict_positive_int(runner_id) is not None else "Empty"


def _state_from_context(
    context: Mapping[str, Any],
    game: Mapping[str, Any],
    *,
    v19_module,
) -> dict[str, Any]:
    ctx = deepcopy(dict(context))
    meta = deepcopy(dict(game))
    game_id = _strict_positive_int(ctx.get("official_game_id"))
    meta_id = _strict_positive_int(meta.get("game_pk"))
    if game_id is None or meta_id != game_id:
        raise RuntimeError("Step 9C exact gamePk metadata boundary failed")

    away_team_id = _strict_positive_int(meta.get("away_team_id"))
    home_team_id = _strict_positive_int(meta.get("home_team_id"))
    if away_team_id is None or home_team_id is None:
        raise RuntimeError("Step 9C legacy team-ID metadata unavailable")

    inning = ctx.get("inning") or "—"
    return {
        "state": str(ctx.get("state") or "PREGAME"),
        "status": str(ctx.get("status") or "Unknown"),
        "away_team": str(ctx.get("away_team") or meta.get("away_team") or "Away"),
        "home_team": str(ctx.get("home_team") or meta.get("home_team") or "Home"),
        "away_team_id": away_team_id,
        "home_team_id": home_team_id,
        "away_runs": _safe_nonnegative_int(ctx.get("away_runs")),
        "home_runs": _safe_nonnegative_int(ctx.get("home_runs")),
        "away_hits": _safe_nonnegative_int(ctx.get("away_hits")),
        "home_hits": _safe_nonnegative_int(ctx.get("home_hits")),
        "away_errors": _safe_nonnegative_int(ctx.get("away_errors")),
        "home_errors": _safe_nonnegative_int(ctx.get("home_errors")),
        "inning": inning,
        "inning_num": v19_module._parse_inning(inning),
        "inning_state": str(ctx.get("inning_state") or "—"),
        "balls": _safe_nonnegative_int(ctx.get("balls")),
        "strikes": _safe_nonnegative_int(ctx.get("strikes")),
        "outs": _safe_nonnegative_int(ctx.get("outs")),
        "batter": str(ctx.get("batter") or "—"),
        "batter_id": _strict_positive_int(ctx.get("batter_id")),
        "pitcher": str(ctx.get("pitcher") or "—"),
        "pitcher_id": _strict_positive_int(ctx.get("pitcher_id")),
        "on_deck": str(ctx.get("on_deck") or "—"),
        "in_hole": str(ctx.get("in_hole") or "—"),
        "first": _occupied_name(ctx.get("first"), ctx.get("runner_first_id")),
        "second": _occupied_name(ctx.get("second"), ctx.get("runner_second_id")),
        "third": _occupied_name(ctx.get("third"), ctx.get("runner_third_id")),
        "last_play": str(ctx.get("last_play") or "Waiting for live play data…"),
        "last_pitch_desc": ctx.get("last_pitch_desc"),
        "last_pitch_type": ctx.get("last_pitch_type"),
        "last_pitch_speed": ctx.get("last_pitch_speed"),
        "recent": deepcopy(list(ctx.get("recent_plays") or [])),
        "updated": datetime.now(v19_module.ET).strftime("%I:%M:%S %p ET").lstrip("0"),
    }


def consumer_status() -> dict[str, Any]:
    return deepcopy(_LAST_STATUS)


def install_step9c_live_state_consumer() -> dict[str, Any]:
    """Install API-first selected-game state transport on the frozen V19 owner."""
    import live_game_hub_v19 as v19

    current_feed = v19.fetch_live_feed
    current_state = v19._state
    current_render = v19._render_selected

    legacy_feed = getattr(current_feed, "_step9c_legacy", current_feed)
    legacy_state = getattr(current_state, "_step9c_legacy", current_state)
    legacy_render = getattr(current_render, "_step9c_legacy", current_render)

    def fetch_live_feed_api_first(game_pk):
        game_id = _strict_positive_int(game_pk)
        if game_id is None:
            return legacy_feed(game_pk)
        meta = deepcopy(_CURRENT_GAME.get() or {})
        meta_id = _strict_positive_int(meta.get("game_pk"))
        game_date = str(meta.get("game_date") or "").strip() or None
        _LAST_STATUS.update({
            "installed": True,
            "api_attempted": True,
            "api_used": False,
            "legacy_fallback_used": False,
            "official_game_id": game_id,
            "failure": None,
        })
        try:
            if meta_id != game_id:
                raise RuntimeError("selected metadata gamePk mismatch")
            if _strict_positive_int(meta.get("away_team_id")) is None or _strict_positive_int(meta.get("home_team_id")) is None:
                raise RuntimeError("legacy team IDs unavailable")
            context = _certified_context(game_id, game_date=game_date)
            if not context:
                raise RuntimeError("Step 9A rejected API live-state context")
            if _strict_positive_int(context.get("official_game_id")) != game_id:
                raise RuntimeError("API context exact gamePk mismatch")
            _LAST_STATUS.update({"api_used": True})
            return {TAG: deepcopy(context)}
        except Exception as exc:
            _LAST_STATUS.update({
                "api_used": False,
                "legacy_fallback_used": True,
                "failure": type(exc).__name__,
            })
            return legacy_feed(game_pk)

    def clear_feed():
        clear = getattr(legacy_feed, "clear", None)
        if callable(clear):
            clear()
        _LAST_STATUS.update({
            "api_attempted": False,
            "api_used": False,
            "legacy_fallback_used": False,
            "official_game_id": None,
            "failure": None,
        })

    fetch_live_feed_api_first.clear = clear_feed
    fetch_live_feed_api_first._step9c_legacy = legacy_feed
    fetch_live_feed_api_first._step9c_wrapper = True

    def state_api_first(feed):
    if isinstance(feed, Mapping) and TAG in feed:
        context = feed.get(TAG)
        meta = _CURRENT_GAME.get()
        try:
            if isinstance(context, Mapping) and isinstance(meta, Mapping):
          return _state_from_context(context, meta, v19_module=v19)
            raise RuntimeError("Step 9C tagged state missing exact selected-game metadata")
        except Exception as exc:
            game_id = _strict_positive_int(
          context.get("official_game_id") if isinstance(context, Mapping) else None
            )
            _LAST_STATUS.update({
          "api_used": False,
          "legacy_fallback_used": True,
          "failure": type(exc).__name__,
            })
            if game_id is not None:
          return legacy_state(legacy_feed(game_id))
            raise
    return legacy_state(feed)

    state_api_first._step9c_legacy = legacy_state
    state_api_first._step9c_wrapper = True

    def render_selected_with_exact_metadata(game, section_header):
        token = _CURRENT_GAME.set(deepcopy(dict(game)) if isinstance(game, Mapping) else None)
        try:
            return legacy_render(game, section_header)
        finally:
            _CURRENT_GAME.reset(token)

    render_selected_with_exact_metadata._step9c_legacy = legacy_render
    render_selected_with_exact_metadata._step9c_wrapper = True

    v19.fetch_live_feed = fetch_live_feed_api_first
    v19._state = state_api_first
    v19._render_selected = render_selected_with_exact_metadata

    _LAST_STATUS.update({"installed": True})
    result = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "installed": True,
        "patched_module": "live_game_hub_v19",
        "selected_game_state_api_first": True,
        "legacy_verified_slate_preserved": True,
        "legacy_live_feed_fallback_preserved": True,
        "match_method": MATCH_METHOD,
        "preexisting_v19_model_preserved": True,
        **{key: False for key in PROTECTED_FALSE_FLAGS},
    }
    return result


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "DEFAULT_API_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "PROTECTED_FALSE_FLAGS",
    "consumer_status",
    "install_step9c_live_state_consumer",
]
