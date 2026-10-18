"""API 2 universal NFL active-slate terminal owner V1.

Runs once at the terminal route boundary for canonical NFL routes. It establishes
shared AUTO/MANUAL NFL date ownership, then delegates through the current terminal
parent unchanged. Non-NFL routes bypass this owner completely.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_monster_cfb_market_completeness_r1 as prior
from nfl_active_slate_runtime_v1 import (
    install_nfl_date_input_bridge,
    prepare_nfl_active_slate,
)

MODEL_VERSION = "API2 UNIVERSAL NFL ACTIVE SLATE V1 • TERMINAL OWNER"
FROZEN_PARENT = "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


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


def _is_nfl_route() -> bool:
    canonical = _value(st.session_state, "ks_universal_sport")
    query = _value(st.query_params, "sport") or _value(st.query_params, "ks_sport")
    return _normalize(canonical or query) == "nfl"


def _prepare_active_slate() -> dict[str, Any]:
    import nfl_hub_v1 as nfl
    from nfl_passing_yards_next_slate_v1 import nflverse_schedule_dates

    today_et = datetime.now(nfl.ET).date()
    return prepare_nfl_active_slate(
        st.session_state,
        today_et=today_et,
        primary_loader=nfl.load_nfl_slate,
        calendar_dates=nflverse_schedule_dates,
    )


def render_app() -> Any:
    if not _is_nfl_route():
        return prior.render_app()

    _prepare_active_slate()
    with install_nfl_date_input_bridge(st.session_state):
        return prior.render_app()


__all__ = [
    "FROZEN_PARENT",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
