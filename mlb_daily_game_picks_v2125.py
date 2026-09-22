"""MLB Daily Game Picks V2.1.2.5 — automatic mid-build 429 handoff.

Controller/orchestration hotfix only. Keeps all production model math, simulation
depths, verified-market gates, Step 3/5/6 rankings, live-risk checks, logos, and
completed connector packs unchanged.

Fixes the remaining 5/7 retry loop:
- if Run Line or Total triggers the sportsbook provider cooldown DURING an active
  Resume pass, the controller automatically stops the doomed pass;
- the retry is immediately armed for the provider reset window;
- the page shows the existing V2.1.2.4 visible countdown and auto-refresh;
- when cooldown expires, Run Line resumes first and Total reuses the same verified
  sportsbook snapshot;
- completed Moneyline/Pitcher K/H+R+RBI/Home Run/1+ Hit connectors never rerun.
"""
from __future__ import annotations

import streamlit as st

import mlb_daily_game_picks_v2124 as previous

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.2.5 • AUTO 429 HANDOFF"

_BASE_BUILD_STAGE = controller._build_stage


def _build_stage_v2125(games_df, stage):
    """Run the native builder, then convert a new sportsbook 429 into an armed wait."""
    built = _BASE_BUILD_STAGE(games_df, stage)

    if stage in {"runline", "total"} and not controller._complete(built):
        cooldown = previous._cooldown_until(games_df)
        if cooldown:
            day = controller._day(games_df)
            # Stop the current V2.0.8 pass after this stage. Its local state object
            # is the same mutable object stored in session_state, so preserving
            # active=False here survives the controller's final write.
            state_key = controller._state_key(day)
            state = st.session_state.get(state_key)
            if isinstance(state, dict):
                state["active"] = False
                st.session_state[state_key] = state

            st.session_state[previous._arm_key(day)] = True
            st.session_state[previous._notice_key(day)] = (
                "Sportsbook rate limit detected during retry. Automatic retry is armed; no additional tap is required."
            )

    return built


# Patch the exact V2.0.8 controller function used by the inherited one-tap builder.
controller._build_stage = _build_stage_v2125


def _auto_arm_existing_cooldown(games_df):
    """Carry a just-triggered 429 into visible armed state after deploy/rerender."""
    day = controller._day(games_df)
    if not day:
        return
    cooldown = previous._cooldown_until(games_df)
    if not cooldown:
        return

    state = st.session_state.get(controller._state_key(day))
    active = bool(isinstance(state, dict) and state.get("active"))
    if active:
        return

    incomplete_sportsbook = any(
        not controller._complete(controller._pack(games_df, stage))
        for stage in ("runline", "total")
    )
    if incomplete_sportsbook:
        st.session_state[previous._arm_key(day)] = True


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    controller._build_stage = _build_stage_v2125
    # The V2.1.2.4 renderer is already patched into controller._render_full_builder.
    _auto_arm_existing_cooldown(games_df)
    st.caption(
        "♻️ V2.1.2.5 retry handoff: a sportsbook 429 during Run Line/Total now automatically arms the visible cooldown retry; no second Resume tap is required."
    )
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
