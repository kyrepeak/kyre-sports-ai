"""WNBA Points V1.9.8 — guaranteed Step 2.2 candidate-card handoff.

Presentation-only wrapper over V1.9.7. It fixes the last visual handoff bug where
the validated 5M Points results rendered the legacy audit table but the enhanced
candidate-card renderer was not reached by the inherited wrapper chain.

No projection, SportsGameOdds, Monte Carlo, calibration, H2H, PRA, or MLB math
is changed. Existing protected 5M/10M summaries are reused.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_points_hub_v197 as prior
import wnba_points_hub_v196 as enhanced

MODEL_VERSION = "WNBA POINTS V1.9.8 • GUARANTEED ENHANCED CARD HANDOFF"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH

visual = prior.visual
points = prior.points
hierarchy = prior.hierarchy

_ORIGINAL_ENHANCED_RENDER = enhanced._render_final_points_board_enhanced
_RENDER_MARKER = "_wnba_points_v198_cards_rendered"


def _current_day() -> str:
    for key in ("wnba_points_date", "wnba_points_date_control"):
        value = st.session_state.get(key)
        if value is not None:
            try:
                return pd.to_datetime(value).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _tracked_enhanced_render(day):
    day = pd.to_datetime(day).strftime("%Y-%m-%d")
    st.session_state[_RENDER_MARKER] = day
    return _ORIGINAL_ENHANCED_RENDER(day)


def _visual_header_v198(day, slate):
    """Reuse the proven V1.9.7 header logic with a truthful V1.9.8 fingerprint."""
    visual._visual_css()

    try:
        rows = points.combined_rows(day)
    except Exception:
        rows = pd.DataFrame()
    distributions = 0
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        keys = [c for c in ("game_id", "player_key", "line") if c in rows.columns]
        distributions = int(rows[keys].drop_duplicates().shape[0]) if len(keys) == 3 else int(len(rows))

    st.markdown(
        """
<div class="kyre-wnba-hero">
  <div class="kyre-wnba-kicker">KYRE SPORTS AI • WNBA POINTS • VISUAL COMMAND CENTER</div>
  <div class="kyre-wnba-title">🏀 WNBA Points Command Center — V1.9.8</div>
  <div class="kyre-wnba-sub">Step 2.2 renderer handoff FIXED • MLB-style matchup presentation • player headshots • player-vs-team history • enhanced Top Points candidate cards • expandable Why this pick? • verified four-game Eastern slate • current rosters • rotation-aware L3/L5 minutes • role/usage • opponent pace + L10 defense • positional matchup • empirical variance • exact SportsGameOdds Points markets. Production model math is unchanged.</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(slate.get("total") or 0))
    c2.metric("Upcoming", int(slate.get("upcoming") or 0))
    pairs = slate.get("pairs")
    market_players = 0 if not isinstance(pairs, pd.DataFrame) or pairs.empty else int(pairs["player_key"].nunique())
    c3.metric("Points market players", market_players)
    c4.metric("Protected distributions", distributions)

    diag = slate.get("diag") or {}
    state = str(diag.get("state") or "UNKNOWN").upper()
    if state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE", "VERIFIED_OFF_DAY"}:
        st.success(
            f"✅ VERIFIED WNBA POINTS SLATE • {day} • "
            f"{int(slate.get('total') or 0)} game(s) • Eastern Time"
        )
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")

    st.info(
        "✨ STEP 2.2 ACTIVE • rich Top Points cards are wired directly to the "
        "protected production result handoff. Visual-only layer; model math unchanged."
    )
    visual._render_matchup_cards(day)
    st.markdown(
        '<div class="kyre-engine-note">⚙️ <b>Production engine room below:</b> '
        "roster, minutes, history, matchup, Monte Carlo and calibration checks stay "
        "visible for auditability. The visual layer does not alter any projection.</div>",
        unsafe_allow_html=True,
    )


def _install_routeproof_hooks():
    # V1.9.7 and V1.9.6 both reinstall hooks on each Streamlit rerun. Replace the
    # function attributes THEY look up, then patch each known live V1.9 module
    # reference as a belt-and-suspenders guard.
    prior._visual_header_v197 = _visual_header_v198
    enhanced._render_final_points_board_enhanced = _tracked_enhanced_render

    visual._visual_header = _visual_header_v198
    visual.core.clean._clean_header = _visual_header_v198

    hierarchy._render_final_points_board = _tracked_enhanced_render
    try:
        visual.core.v19._render_final_points_board = _tracked_enhanced_render
    except Exception:
        pass
    try:
        visual.core.clean.v19._render_final_points_board = _tracked_enhanced_render
    except Exception:
        pass


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = _current_day()

    # Keep V1.9.7's early snapshot restore. It never runs simulations.
    restored = prior._try_early_restore(day)
    if restored:
        st.toast("💾 Restored completed WNBA Points snapshot — no 5M rerun required.")
        st.rerun()

    # Run-local marker: if an inherited module still bypasses the patched hook,
    # append the rich cards explicitly after the validated production UI returns.
    st.session_state[_RENDER_MARKER] = ""
    _install_routeproof_hooks()
    result = prior.render_wnba_points_hub(section_header, status_info, team_logo, h)

    if st.session_state.get(_RENDER_MARKER) != day:
        st.divider()
        st.caption(
            "✨ V1.9.8 direct result handoff • the rich candidate layer below reads "
            "the existing protected Points simulation output; no new simulation is run."
        )
        _tracked_enhanced_render(day)
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
