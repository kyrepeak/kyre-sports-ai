"""MLB Daily Game Picks V2.1.2.4 — visible sportsbook cooldown + armed resume.

Controller/UI hotfix only. Keeps V2.1.2.3 live-risk semantics and every existing
production model unchanged. Fixes the confusing 5/7 Resume behavior for Run Line
+ Total when the sportsbook provider is rate-limited:
- a Resume tap during provider cooldown visibly arms the retry instead of appearing
  to do nothing;
- the page shows the provider reset time/countdown;
- a lightweight display-only autorefresh checks the cooldown window;
- when the cooldown expires, the controller automatically resumes at the first
  incomplete stage;
- already-complete Moneyline/Pitcher K/H+R+RBI/HR/1+ Hit packs are skipped.
"""
from __future__ import annotations

import time

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

import mlb_daily_game_picks_v2123 as previous
import mlb_daily_game_picks_v205 as quota

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.2.4 • ARMED SPORTSBOOK RESUME"


def _cooldown_until(games_df):
    day = controller._day(games_df)
    if not day:
        return None
    key = quota._cooldown_key(day)
    raw = st.session_state.get(key)
    try:
        epoch = float(raw)
    except Exception:
        return None
    if epoch <= time.time():
        st.session_state.pop(key, None)
        return None
    return epoch


def _remaining_seconds(epoch):
    try:
        return max(0, int(round(float(epoch) - time.time())))
    except Exception:
        return 0


def _fmt_wait(seconds):
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return f"{seconds}s"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"{mins}m {secs:02d}s"
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins:02d}m"


def _arm_key(day):
    return f"dgp_fullcard_resume_armed_v2124::{day}"


def _notice_key(day):
    return f"dgp_fullcard_resume_notice_v2124::{day}"


def _start_controller(games_df, state_key, prior_state):
    """Start a fresh controller pass while preserving all native connector packs."""
    day = controller._day(games_df)
    fresh = controller._initial_state(day)
    fresh["active"] = True
    fresh["runs"] = int((prior_state or {}).get("runs", 0) or 0) + 1
    st.session_state[state_key] = fresh
    st.session_state[_arm_key(day)] = False
    st.session_state[_notice_key(day)] = "Retry started. Completed connectors will be skipped."
    st.rerun()


def _render_full_builder_v2124(games_df):
    day = controller._day(games_df)
    if not day:
        return

    key = controller._state_key(day)
    state = st.session_state.get(key)
    if not isinstance(state, dict) or state.get("day") != day:
        state = controller._initial_state(day)
        st.session_state[key] = state

    st.markdown("### 🚀 One-Tap Full MLB Card")
    done = controller._completed_count(games_df)
    st.caption(
        "Runs all seven existing production connectors in order, skips completed work, resumes partial work, and automatically feeds Step 5 + the Daily Master Card. No model math is changed."
    )
    st.progress(done / len(controller.STAGES), text=f"Full MLB Card • {done}/7 connectors complete")
    st.caption(controller._summary(games_df))

    # Existing active build continues through the proven V2.0.8 controller.
    if state.get("active"):
        controller._run_controller(games_df, key, state)
        return

    if controller._all_complete(games_df):
        st.session_state[_arm_key(day)] = False
        st.success("✅ FULL MLB CARD READY • 7/7 production connectors complete • Step 5 and Daily Master Card are live below.")
        return

    blocked = dict(state.get("blocked") or {})
    if blocked:
        st.warning(
            f"{done}/7 connectors are complete. Only unfinished connectors will be retried; completed connectors remain cached and are skipped."
        )
        with st.expander(f"⚠️ Full-card blocked-stage notes ({len(blocked)})"):
            for stage, message in blocked.items():
                label = next((x[1] for x in controller.STAGES if x[0] == stage), stage)
                st.caption(f"• {label}: {message}")

    cooldown = _cooldown_until(games_df)
    armed = bool(st.session_state.get(_arm_key(day), False))

    # A prior Resume tap can wait visibly for a provider 429 window to reopen.
    if armed:
        if cooldown:
            remaining = _remaining_seconds(cooldown)
            reset_text = quota._fmt_reset(cooldown)
            st.info(
                f"⏳ Run Line + Total retry is ARMED. Sportsbook provider cooldown has about {_fmt_wait(remaining)} remaining (reset: {reset_text}). The five completed connectors will not rerun."
            )
            st.progress(
                0.0,
                text=f"Waiting for sportsbook provider • auto-retry in about {_fmt_wait(remaining)}",
            )
            if st_autorefresh is not None:
                st_autorefresh(interval=5000, key=f"dgp_resume_wait_refresh_v2124::{day}")
            else:
                st.caption("Display auto-refresh is unavailable; refresh the page after the reset time and the armed retry will continue.")
            if st.button("✖ CANCEL ARMED RETRY", use_container_width=True, key=f"dgp_cancel_resume_v2124::{day}"):
                st.session_state[_arm_key(day)] = False
                st.rerun()
            return

        # Cooldown expired. Turn the armed wait into a real controller pass.
        st.session_state[_arm_key(day)] = False
        _start_controller(games_df, key, state)
        return

    notice = st.session_state.pop(_notice_key(day), None)
    if notice:
        st.success(str(notice))

    label = "▶ RESUME FULL MLB CARD" if done else "🚀 BUILD TODAY'S FULL MLB CARD"
    if st.button(label, type="primary", use_container_width=True, key=f"dgp_fullcard_start_v2124::{day}"):
        cooldown = _cooldown_until(games_df)
        if cooldown:
            # Do not make a doomed provider call. Arm one automatic retry instead.
            st.session_state[_arm_key(day)] = True
            st.session_state[_notice_key(day)] = "Sportsbook retry armed."
            st.rerun()
        else:
            _start_controller(games_df, key, state)


# Patch the inherited renderer where V2.0.9/V2.1.x resolve it at runtime.
controller._render_full_builder = _render_full_builder_v2124


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    controller._render_full_builder = _render_full_builder_v2124
    st.caption(
        "🔁 V2.1.2.4 resume controller: provider cooldown is visible • Resume can arm an automatic Run Line/Total retry • completed connectors stay cached."
    )
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
