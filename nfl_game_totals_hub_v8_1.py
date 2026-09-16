"""NFL Game Totals V8.1 — additive mobile empty-slate recovery hotfix.

Preserves certified V8 projection behavior verbatim. This layer only improves
calendar navigation and targeted cache refresh so an empty current NFL date does
not leave mobile users staring at a blank slate with no recovery control.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v8 as v8
from sports_api.nfl_data_router_v1 import clear_router_caches
from sports_api.nfl_game_totals_mobile_navigation_v1 import find_next_game_day

MODEL_VERSION = "NFL GAME TOTALS V8.1 • MOBILE EMPTY-SLATE HOTFIX • STEP 8 PRESERVED"
PAGE_BUILD_STEP = 8
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
TOTAL_PROJECTION_ENABLED = True
MARKET_COMPARISON_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True
GAME_ENVIRONMENT_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
AUTO_ADVANCE_EMPTY_TODAY = True
NEXT_SLATE_LOOKAHEAD_DAYS = 14
_PENDING_DATE_KEY = "nfl_game_totals_v8_1_pending_date"
_WIDGET_DATE_KEY = "nfl_game_totals_v8_1_date_input"
_FEEDBACK_KEY = "nfl_game_totals_v8_1_feedback"

_DATE_STATE_KEYS = (
    "nfl_game_totals_v8_1_date",
    "nfl_game_totals_v8_date",
    "nfl_game_totals_v7_date",
    "nfl_game_totals_v6_date",
    "nfl_game_totals_v5_date",
    "nfl_game_totals_v4_date",
    "nfl_game_totals_v3_date",
    "nfl_game_totals_v2_date",
    "nfl_game_totals_v1_date",
    "nfl_v1_date",
)


def _as_date(value: Any, fallback: date) -> date:
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def _sync_game_totals_date(target: date) -> None:
    for key in _DATE_STATE_KEYS:
        st.session_state[key] = target


def _apply_pending_date(today: date) -> None:
    pending = st.session_state.pop(_PENDING_DATE_KEY, None)
    if pending is None:
        return
    target = _as_date(pending, today)
    st.session_state[_WIDGET_DATE_KEY] = target
    _sync_game_totals_date(target)


def _initial_date(today: date) -> date:
    existing = st.session_state.get(
        _WIDGET_DATE_KEY,
        st.session_state.get(
            "nfl_game_totals_v8_1_date",
            st.session_state.get(
                "nfl_game_totals_v8_date",
                st.session_state.get("nfl_v1_date", today),
            ),
        ),
    )
    return _as_date(existing, today)


def _auto_surface_next_slate(selected: date, today: date) -> date:
    should_auto_advance = AUTO_ADVANCE_EMPTY_TODAY and selected == today
    if not should_auto_advance:
        return selected

    day_str = selected.isoformat()
    games, diag = v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or diag.get("request_ok") is not True or not games.empty:
        return selected

    result = find_next_game_day(
        selected,
        v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate,
        max_days=NEXT_SLATE_LOOKAHEAD_DAYS,
    )
    if result.get("ready") is not True or result.get("date") is None:
        return selected

    target = result["date"]
    st.session_state[_WIDGET_DATE_KEY] = target
    _sync_game_totals_date(target)
    st.session_state[_FEEDBACK_KEY] = f"📅 Today has no NFL games, so Game Totals opened the next verified slate: {target.isoformat()}."
    return target


def _clear_game_totals_caches() -> int:
    """Clear only cache functions owned by the Game Totals V1-V8 stack."""
    cached_functions = (
        v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate,
        v8.v7.v6.v5.v4.v3.v2._cached_market_batch,
        v8.v7.v6.v5.v4.v3._cached_team_profiles,
        v8.v7.v6.v5.v4._cached_pace_profiles,
        v8.v7.v6.v5._cached_explosive_profiles,
        v8.v7.v6._cached_red_zone_drive_profiles,
        v8.v7._cached_environment_contexts,
    )
    cleared = 0
    for function in cached_functions:
        clear = getattr(function, "clear", None)
        if callable(clear):
            clear()
            cleared += 1
    clear_router_caches()
    cleared += 1
    return cleared


def _queue_next_game_day(selected: date) -> None:
    result = find_next_game_day(
        selected,
        v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate,
        max_days=NEXT_SLATE_LOOKAHEAD_DAYS,
    )
    if result.get("ready") is True and result.get("date") is not None:
        target = result["date"]
        st.session_state[_PENDING_DATE_KEY] = target.isoformat()
        st.session_state[_FEEDBACK_KEY] = f"➡️ Jumped to next verified NFL game day: {target.isoformat()}."
    else:
        st.session_state[_FEEDBACK_KEY] = f"⚠️ {result.get('reason') or 'No later verified NFL slate was found.'}"
    st.rerun()


def _reload_game_totals_data() -> None:
    cleared = _clear_game_totals_caches()
    st.session_state[_FEEDBACK_KEY] = f"🔄 Game Totals data reloaded. Cleared {cleared} targeted cache layer(s)."
    st.rerun()


def _render_mobile_controls(selected: date) -> None:
    st.markdown("#### 📱 Game Day Controls")
    if st.button("➡️ Next Game Day", key="nfl_game_totals_v8_1_next_day", use_container_width=True):
        _queue_next_game_day(selected)
    if st.button("🔄 Reload Data", key="nfl_game_totals_v8_1_reload", use_container_width=True):
        _reload_game_totals_data()


def render_nfl_game_totals_hub() -> None:
    v8._render_hero()

    today = pd.Timestamp.now(tz=v8.v7.v6.v5.v4.v3.v2.foundation.ET).date()
    _apply_pending_date(today)
    selected = _initial_date(today)
    selected = _auto_surface_next_slate(selected, today)

    selected = st.date_input(
        "📅 NFL Game Totals slate date",
        value=selected,
        key=_WIDGET_DATE_KEY,
    )
    selected = _as_date(selected, today)
    _sync_game_totals_date(selected)

    feedback = st.session_state.pop(_FEEDBACK_KEY, None)
    if feedback:
        st.info(str(feedback))

    _render_mobile_controls(selected)

    day_str = selected.isoformat()
    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate(day_str)

    v8._render_schedule(games, day_str, diag)
    if isinstance(diag, dict) and diag.get("request_ok") is True and games.empty:
        st.info(
            "No verified NFL games were returned for this date. Tap **Next Game Day** above to jump to the next verified slate, or **Reload Data** to refresh Game Totals without rebooting Streamlit."
        )

    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • projection ON • market comparison OFF • live market ON • Steps 3-7 context ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V8.1 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "AUTO_ADVANCE_EMPTY_TODAY",
    "EXPLOSIVE_SCORING_ENABLED",
    "GAME_ENVIRONMENT_ENABLED",
    "LIVE_MARKET_ENABLED",
    "MARKET_COMPARISON_ENABLED",
    "MODEL_VERSION",
    "OFFENSE_DEFENSE_ENABLED",
    "PACE_POSSESSION_ENABLED",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PROJECTION_MODEL_ENABLED",
    "RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TOTAL_PROJECTION_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_clear_game_totals_caches",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
