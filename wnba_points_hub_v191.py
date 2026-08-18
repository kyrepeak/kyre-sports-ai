"""WNBA Points V1.9.1 — UI-only cleanup over validated V1.9.

Keeps V1.9 projection/simulation math unchanged. Removes inherited legacy
version captions and replaces the old V1.7 command-center header with one
clean V1.9 production header.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_points_hub_v19 as v19

MODEL_VERSION = "WNBA POINTS V1.9.1 • CLEAN COMMAND CENTER"
PRA_FROZEN_BRANCH = v19.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = v19.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = v19.MLB_FROZEN_BRANCH


def _clean_header(day, slate):
    current = v19.points.combined_rows(day)
    distributions = 0
    if isinstance(current, pd.DataFrame) and not current.empty:
        needed = [c for c in ("game_id", "player_key", "line") if c in current.columns]
        distributions = int(current[needed].drop_duplicates().shape[0]) if needed else 0

    st.markdown("""
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.9</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">Four-game Eastern-time slate • strict current rosters • rotation-aware L3/L5 minutes • scoring role/usage • recent + season form • opponent pace + L10 defense • verified Guard/Wing/Big scoring matchup • empirical variance • exact SportsGameOdds Points markets. PRA V3.2.1 and MLB V2.1.7 remain frozen.</div>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", slate["total"])
    c2.metric("Upcoming", slate["upcoming"])
    c3.metric("Points market players", 0 if slate["pairs"].empty else int(slate["pairs"]["player_key"].nunique()))
    c4.metric("5M distributions", distributions)

    diag = slate.get("diag") or {}
    state = str(diag.get("state") or "UNKNOWN").upper()
    if state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE", "VERIFIED_OFF_DAY"}:
        st.success(f"✅ Verified WNBA slate • {day} • all {slate['total']} game(s) shown • slate date = Eastern Time")
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")
    counts = diag.get("source_selected_counts") or {}
    if counts:
        st.caption("🧭 Schedule cross-check — " + " • ".join(f"{name}: {count}" for name, count in counts.items()))


def _is_legacy_version_caption(body) -> bool:
    text = str(body or "").strip()
    return any(text.startswith(prefix) for prefix in (
        "🏀 WNBA Points V1.9 •",
        "🏀 WNBA Points V1.8 •",
        "🏀 WNBA Points V1.7.1 •",
        "🏀 WNBA Points V1.7 •",
    ))


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # The inherited render chain is intentionally preserved because it owns the
    # validated readiness, rotation, history, position-matchup and production
    # hooks. Only presentation/version chrome is cleaned here.
    v19.v18.v171.base._render_header = _clean_header

    original_caption = st.caption

    def _caption_filtered(body, *args, **kwargs):
        if _is_legacy_version_caption(body):
            return None
        return original_caption(body, *args, **kwargs)

    original_caption(
        "🏀 WNBA Points V1.9 • full production input stack active • position matchup verified • PRA V3.2.1 frozen • MLB V2.1.7 frozen"
    )
    st.caption = _caption_filtered
    try:
        return v19.render_wnba_points_hub(section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH", "render_wnba_points_hub",
]
