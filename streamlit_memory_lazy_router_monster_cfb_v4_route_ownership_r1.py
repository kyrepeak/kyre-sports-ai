"""MONSTER CFB Game Total ownership gate above Universal Navigation V4.

Exact CFB -> Game Total routes bypass V4's terminal legacy-root guard and enter
the existing production chain that already owns MONSTER CFB Page 1/Page 2 and
the #1627 Daily Slate latency installer. Every other route delegates to V4
unchanged. No model, source, projection, probability, ranking, or API2 routing
behavior is modified.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v4 as prior
import streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1 as cfb_production

MODEL_VERSION = "MONSTER CFB GAME TOTAL V4 ROUTE OWNERSHIP R1"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v4"
CFB_PRODUCTION_CHAIN = "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _value(mapping: Mapping[str, Any], key: str) -> str:
    try:
        raw = mapping.get(key)
    except Exception:
        raw = None
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None
    return str(raw or "").strip()


def _normalize(value: str) -> str:
    return "-".join(str(value or "").strip().lower().replace("_", " ").split())


def _is_cfb_game_total_route() -> bool:
    query_sport = _value(st.query_params, "sport") or _value(st.query_params, "ks_sport")
    query_market = _value(st.query_params, "market") or _value(st.query_params, "ks_cfb_market")
    sport = query_sport or _value(st.session_state, "ks_universal_sport")
    market = query_market or _value(st.session_state, "ks_universal_market")
    return _normalize(sport) in {"cfb", "college-football"} and _normalize(market) == "game-total"


def render_app() -> Any:
    if _is_cfb_game_total_route():
        return cfb_production.render_app()
    return prior.render_app()


__all__ = [
    "CFB_PRODUCTION_CHAIN",
    "FROZEN_PARENT",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "_is_cfb_game_total_route",
    "record_bootstrap_import_ms",
    "render_app",
]
