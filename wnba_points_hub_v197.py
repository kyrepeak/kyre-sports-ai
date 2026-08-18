"""WNBA Points V1.9.7 — route-proof Step 2.2 + early snapshot restore.

Presentation/recovery wrapper over V1.9.6. It does not change Points projection,
SportsGameOdds grading, Monte Carlo, calibration, H2H math, PRA or MLB math.

Fixes two UI/redeploy problems:
1) V1.9.3's visual header was intentionally hard-coded, making newer visual
   wrappers look stale even when they were active.
2) completed V1.9 Points summaries could be restored only later in the inherited
   page, so the top header could render 0 protected distributions after a deploy.

V1.9.7 restores the existing V1.9 persistent snapshot before the visual header
when possible and installs an explicit V1.9.7 header on every Streamlit rerun.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_points_hub_v196 as enhanced

MODEL_VERSION = "WNBA POINTS V1.9.7 • ROUTE-PROOF ENHANCED CARDS"
PRA_FROZEN_BRANCH = enhanced.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = enhanced.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = enhanced.MLB_FROZEN_BRANCH

# V1.9.6 -> V1.9.5 -> V1.9.4. V1.9.4 exposes the V1.9.3 visual module.
visual = enhanced.base.visual
points = enhanced.points
hierarchy = enhanced.hierarchy


def _current_day() -> str:
    for key in ("wnba_points_date", "wnba_points_date_control"):
        value = st.session_state.get(key)
        if value is not None:
            try:
                return pd.to_datetime(value).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _try_early_restore(day: str) -> bool:
    """Reuse the existing V1.9 snapshot; never runs a simulation."""
    try:
        rows = points.combined_rows(day)
    except Exception:
        rows = pd.DataFrame()
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        return False
    try:
        return bool(points.restore_if_missing(day))
    except Exception:
        return False


def _visual_header_v197(day, slate):
    """V1.9.3 visual layout with a truthful current-version fingerprint."""
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
  <div class="kyre-wnba-title">🏀 WNBA Points Command Center — V1.9.7</div>
  <div class="kyre-wnba-sub">Step 2.2 ACTIVE • MLB-style matchup presentation • player headshots • player-vs-team history • enhanced Top Points candidate cards • expandable Why this pick? • verified four-game Eastern slate • current rosters • rotation-aware L3/L5 minutes • role/usage • opponent pace + L10 defense • positional matchup • empirical variance • exact SportsGameOdds Points markets. Production model math is unchanged.</div>
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

    st.info("✨ STEP 2.2 ACTIVE • enhanced Top Points cards + 🧠 Why this pick? are installed below the production results. Visual-only layer; model math unchanged.")
    visual._render_matchup_cards(day)
    st.markdown(
        '<div class="kyre-engine-note">⚙️ <b>Production engine room below:</b> roster, minutes, history, matchup, Monte Carlo and calibration checks stay visible for auditability. The visual layer does not alter any projection.</div>',
        unsafe_allow_html=True,
    )


def _install_hooks():
    # V1.9.3 re-installs its own header each rerun, so replace the function it
    # looks up AND the current clean-header hook before entering inherited code.
    visual._visual_header = _visual_header_v197
    visual.core.clean._clean_header = _visual_header_v197
    # Reinstall V1.9.6's enhanced candidate renderer for the same reason.
    hierarchy._render_final_points_board = enhanced._render_final_points_board_enhanced


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = _current_day()
    restored = _try_early_restore(day)
    if restored:
        st.toast("💾 Restored completed WNBA Points snapshot before page render — no 5M rerun required.")
        st.rerun()

    _install_hooks()
    return enhanced.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
