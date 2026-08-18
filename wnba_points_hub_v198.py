"""WNBA Points V1.9.8 — hot-reload-safe enhanced candidate-card handoff.

Presentation/recovery wrapper over V1.9.7. This fixes the Streamlit hot-reload
alias collision where the legacy compatibility map could make an import of
wnba_points_hub_v196 resolve to the V1.9.7 wrapper instead of the real V1.9.6
module object. We now obtain the already-loaded real enhanced module through
V1.9.7's own reference (`prior.enhanced`) and never re-import that aliased name.

No projection, SportsGameOdds, Monte Carlo, calibration, persistence, H2H, PRA,
or MLB math is changed. Existing protected 5M/10M summaries are reused.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_points_hub_v197 as prior

MODEL_VERSION = "WNBA POINTS V1.9.8 • HOT-RELOAD-SAFE ENHANCED CARDS"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH

# IMPORTANT: do not import wnba_points_hub_v196 by name here. Older app shells
# intentionally alias that name in sys.modules on Streamlit reruns. V1.9.7 kept
# a direct reference to the genuine loaded V1.9.6 module before those aliases
# were installed, so this is the stable hot-reload-safe route.
enhanced = prior.enhanced
visual = prior.visual
points = prior.points
hierarchy = prior.hierarchy

_ORIGINAL_ENHANCED_RENDER = getattr(enhanced, "_render_final_points_board_enhanced", None)
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
    if callable(_ORIGINAL_ENHANCED_RENDER):
        return _ORIGINAL_ENHANCED_RENDER(day)
    # Defensive fallback: the genuine V1.9.6 object should always expose the
    # renderer, but never crash the app if a stale process somehow lacks it.
    st.warning("⚠️ Enhanced Points cards are waiting for the visual module to refresh. Protected simulation results remain intact.")
    return None


def _visual_header_v198(day, slate):
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
  <div class="kyre-wnba-sub">Hot-reload-safe Step 2.2 • enhanced Top Points candidate cards • player headshots • team logos • descriptive H2H • expandable Why this pick? • protected 5M/10M simulation reuse. Production model math is unchanged.</div>
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
        st.success(f"✅ VERIFIED WNBA POINTS SLATE • {day} • {int(slate.get('total') or 0)} game(s) • Eastern Time")
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")

    st.info("✨ STEP 2.2 ACTIVE • rich Top Points cards read the existing protected production output; no new simulation is triggered by this visual layer.")
    visual._render_matchup_cards(day)
    st.markdown(
        '<div class="kyre-engine-note">⚙️ <b>Production engine room below:</b> roster, minutes, history, matchup, Monte Carlo and calibration checks stay visible for auditability. The visual layer does not alter any projection.</div>',
        unsafe_allow_html=True,
    )


def _install_routeproof_hooks():
    # V1.9.7 re-installs these on every rerun, so replace the exact globals that
    # its installer reads before delegating into the inherited production page.
    prior._visual_header_v197 = _visual_header_v198
    if callable(_ORIGINAL_ENHANCED_RENDER):
        enhanced._render_final_points_board_enhanced = _tracked_enhanced_render

    visual._visual_header = _visual_header_v198
    visual.core.clean._clean_header = _visual_header_v198
    hierarchy._render_final_points_board = _tracked_enhanced_render

    # Belt-and-suspenders: patch known live V1.9 references when present.
    for obj in (
        getattr(visual.core, "v19", None),
        getattr(getattr(visual.core, "clean", None), "v19", None),
    ):
        if obj is not None:
            try:
                obj._render_final_points_board = _tracked_enhanced_render
            except Exception:
                pass


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = _current_day()

    # Reuse V1.9.7 persistence recovery. This never runs Monte Carlo.
    restored = prior._try_early_restore(day)
    if restored:
        st.toast("💾 Restored completed WNBA Points snapshot — no 5M rerun required.")
        st.rerun()

    st.session_state[_RENDER_MARKER] = ""
    _install_routeproof_hooks()
    result = prior.render_wnba_points_hub(section_header, status_info, team_logo, h)

    # If an inherited renderer still bypasses every patched hook, render the
    # enhanced cards explicitly from the same protected rows after production UI.
    if st.session_state.get(_RENDER_MARKER) != day and callable(_ORIGINAL_ENHANCED_RENDER):
        st.divider()
        st.caption("✨ V1.9.8 direct protected-result handoff • no new simulation is run.")
        _tracked_enhanced_render(day)
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
