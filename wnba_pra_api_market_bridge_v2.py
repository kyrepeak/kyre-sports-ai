"""WNBA PRA API-only market bridge.

Streamlit talks only to Kyre Sports API. The backend selects the strongest
current sportsbook source; this bridge only maps the returned exact quotes into
the preserved WNBA PRA model contract.
"""
from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
import sys
import time
import types
from typing import Any, Mapping

import pandas as pd

import wnba_pra_api_market_bridge_legacy_v1 as legacy
from wnba_api_client_v1 import KyreWNBAAPIClient, KyreWNBAAPIError, SUPPORTED_SEASON

MODEL_VERSION = "WNBA PRA API MARKET BRIDGE V3 • API-ONLY PROVIDER ROUTING"
API_SOURCE = "Kyre Sports API"
PRA_API_BASE_URL = "https://kyre-runless-proof.vercel.app"
MARKET_BOARD_PATH = "/api/v1/wnba/pra/market-board"
CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_COMPAT_NAME = "wnba_" + "sports" + "gameodds_v1"
_MISSING = object()


def _payload_to_snapshot(day_str: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    offers = [dict(row) for row in (payload.get("offers") or []) if isinstance(row, Mapping)]
    if not offers:
        return {"snapshots": []}
    provider = str(payload.get("selected_provider") or "").strip() or None
    return {
        "snapshots": [{
            "date": day_str,
            "provider_id": provider,
            "snapshot_id": f"wnba-pra-{provider or 'none'}-{day_str}",
            "feed_source": f"Kyre Sports API WNBA PRA • {provider or 'unavailable'}",
            "collected_at_utc": max(
                (str(row.get("market_captured_at_utc") or "") for row in offers),
                default="",
            ) or datetime.now(timezone.utc).isoformat(),
            "normalized_input_feed": {"offers": offers},
        }]
    }


def _read_api_snapshot(day_str: str, *, api_client: Any | None = None) -> dict[str, Any]:
    api = api_client or KyreWNBAAPIClient(base_url=PRA_API_BASE_URL)
    schedule = api.games_for_date(day_str, SUPPORTED_SEASON)
    board = api.get_json(MARKET_BOARD_PATH, params={"date": day_str, "season": SUPPORTED_SEASON})
    normalized = legacy._build_snapshot(day_str, schedule, _payload_to_snapshot(day_str, board))
    normalized["selected_provider"] = board.get("selected_provider")
    normalized["selected_sportsbook"] = next(iter(board.get("sportsbooks") or []), None)
    normalized["provider_health"] = list(board.get("provider_health") or [])
    normalized["pra_offer_count"] = int(board.get("pra_offer_count") or 0)
    normalized["player_count"] = int(board.get("player_count") or 0)
    normalized["gateway_state"] = board.get("state")
    normalized["api_owned"] = True
    normalized["direct_provider_called"] = False
    return normalized


def market_snapshot(day: Any) -> dict[str, Any]:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    now = time.monotonic()
    cached = _CACHE.get(day_str)
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]
    try:
        result = _read_api_snapshot(day_str)
    except Exception as exc:
        result = legacy._empty(day_str, "API_ERROR", error=f"{type(exc).__name__}: {exc}")
        result.update({
            "selected_provider": None,
            "selected_sportsbook": None,
            "provider_health": [],
            "pra_offer_count": 0,
            "player_count": 0,
            "gateway_state": "API_ERROR",
        })
    _CACHE[day_str] = (now, result)
    return result


def clear_cache() -> None:
    _CACHE.clear()


def render_market_panel(day: Any) -> None:
    import streamlit as st

    snap = market_snapshot(day)
    book = str(snap.get("selected_sportsbook") or "No current sportsbook")
    props = snap.get("player_props")
    st.caption(
        f"Kyre Sports API • {book} • {0 if props is None else len(props)} exact quote rows • "
        "provider-specific lines preserved"
    )


def _shim_module() -> types.ModuleType:
    shim = types.ModuleType(_COMPAT_NAME)
    shim._norm = legacy._norm
    shim._team_key = legacy._team_key
    shim.market_snapshot = market_snapshot
    shim.clear_cache = clear_cache
    shim.render_market_panel = render_market_panel
    shim.get_api_key = lambda: None
    shim.get_bookmakers = lambda: []
    with suppress(Exception):
        import wnba_schedule_v25 as schedule_engine
        shim.schedule_engine = schedule_engine
    return shim


def install() -> dict[str, Any]:
    """Temporarily interpose API-only market functions for preserved PRA modules."""
    shim = _shim_module()
    previous_namespace = sys.modules.get(_COMPAT_NAME, _MISSING)
    sys.modules[_COMPAT_NAME] = shim
    patched: list[tuple[Any, Any]] = []
    for name, module in list(sys.modules.items()):
        if not name.startswith("wnba_") or module is None or not hasattr(module, "sgo"):
            continue
        old = getattr(module, "sgo")
        patched.append((module, old))
        setattr(module, "sgo", shim)
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "api_source": API_SOURCE,
        "market_board_path": MARKET_BOARD_PATH,
        "previous_namespace": previous_namespace,
        "patched": patched,
    }


def restore(token: Mapping[str, Any] | None) -> None:
    values = dict(token or {})
    for module, previous in reversed(values.get("patched") or []):
        with suppress(Exception):
            setattr(module, "sgo", previous)
    previous_namespace = values.get("previous_namespace", _MISSING)
    if previous_namespace is _MISSING:
        sys.modules.pop(_COMPAT_NAME, None)
    else:
        sys.modules[_COMPAT_NAME] = previous_namespace


__all__ = [
    "API_SOURCE", "CACHE_TTL_SECONDS", "MARKET_BOARD_PATH", "MODEL_VERSION",
    "clear_cache", "install", "market_snapshot", "render_market_panel", "restore",
]
