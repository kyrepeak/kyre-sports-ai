"""MLB Matchup Explorer V2 — Steps 1-2 player intelligence stack.

Step 2 adds a player-only true-talent hit profile on top of the certified Step 1
foundation. The frozen V1 Matchup model, rankings, moneyline and final probability
math remain untouched. No game-level 1+ hit probability is calculated here.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hitter_profile_v1 as hitter_profile
import mlb_matchup_hub_v10 as ui
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1

VERSION = "MLB Matchup Intelligence V2 Step 2"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP2_ROLE = "PLAYER_SKILL_PROFILE_ONLY"


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _fmt_avg(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "—"


def _fmt_num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _esc(value: Any) -> str:
    return ui._esc(value)


def _build_profile(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    player_id = foundation.get("player_id")
    season = foundation.get("season")
    if not player_id or not season:
        return hitter_profile.build_hitter_profile(foundation, [], None)

    try:
        logs = ui._game_logs(int(player_id), int(season))
    except Exception:
        logs = []
    try:
        savant = hitter_profile.fetch_savant_profile(int(player_id), int(season))
    except Exception:
        savant = None
    return hitter_profile.build_hitter_profile(foundation, logs, savant)


def _render_step2(games_df) -> None:
    d = _build_profile(games_df)
    if not d:
        st.warning("Step 2 hitter profile is waiting for a verified player selection.")
        return

    weights = d.get("skill_weights") or {}
    weight_text = (
        f"season {_fmt_rate(weights.get('season'))} • "
        f"xBA {_fmt_rate(weights.get('xba'))} • "
        f"recent {_fmt_rate(weights.get('recent'))}"
    )
    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("profile_components") or {}).items()
    )
    expected_hits = _fmt_num(d.get("expected_hits"), 1)
    neutral_skill = _fmt_avg(d.get("neutral_hit_skill"))
    recent_label = (
        f"{_fmt_avg(d.get('recent_avg'))} over {int(d.get('recent_ab') or 0)} AB / "
        f"{int(d.get('recent_games') or 0)} games"
    )

    st.markdown(
        f'''<div class="mxv2-step mxv2-step2">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 2 • HITTER TRUE-TALENT HIT PROFILE</div>
            <div class="mxv2-badge">{_esc(d['profile_quality_label'])} • {int(d['profile_score'])}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d['player_name'])}</b> • neutral hitter skill before matchup effects</div>
          <div class="mxv2-status">Player-only profile • probability impact: NONE • no starter/park/bullpen/game-PA adjustment yet</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Season AVG</span><b>{_fmt_avg(d.get('season_avg'))}</b></div>
            <div class="mxv2-mini"><span>xBA</span><b>{_fmt_avg(d.get('xba'))}</b></div>
            <div class="mxv2-mini"><span>Hits / PA</span><b>{_fmt_rate(d.get('hit_per_pa'))}</b></div>
            <div class="mxv2-mini"><span>Neutral skill</span><b>{neutral_skill}</b></div>
            <div class="mxv2-mini"><span>Contact</span><b>{_fmt_rate(d.get('contact_pct'))}</b></div>
            <div class="mxv2-mini"><span>Zone contact</span><b>{_fmt_rate(d.get('zone_contact_pct'))}</b></div>
            <div class="mxv2-mini"><span>Whiff</span><b>{_fmt_rate(d.get('whiff_pct'))}</b></div>
            <div class="mxv2-mini"><span>K rate</span><b>{_fmt_rate(d.get('k_pct'))}</b></div>
            <div class="mxv2-mini"><span>Hard-hit</span><b>{_fmt_rate(d.get('hard_hit_pct'))}</b></div>
            <div class="mxv2-mini"><span>BABIP</span><b>{_fmt_avg(d.get('babip'))}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Expected-hit check</b> • Statcast xBA × current season AB = {expected_hits} xH through this sample • this is not a next-game hit projection.</div>
          <div class="mxv2-row"><b>BABIP sustainability</b> • {_esc(d.get('babip_label'))} • {_esc(d.get('babip_note'))}</div>
          <div class="mxv2-row"><b>Weighted recent form</b> • {recent_label} • exponential decay prevents one hot game from owning the profile.</div>
          <div class="mxv2-row"><b>Neutral skill blend</b> • {neutral_skill} • {_esc(weight_text)} • sample-shrunk before any matchup layer.</div>
          <div class="mxv2-row"><b>Statcast context</b> • {_esc(d.get('savant_source'))} • {int(d.get('savant_pa') or 0)} PA • {int(d.get('savant_bbe') or 0)} BBE • Avg EV {_fmt_num(d.get('avg_ev'), 1)} • Barrel {_fmt_rate(d.get('barrel_pct'))}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Profile completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 2 describes hitter skill only. P(0), P(1+), P(2+), fair odds, Monte Carlo and final grades remain reserved for later V2 steps.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if str(d.get("savant_source")) == "UNAVAILABLE":
        st.warning("Step 2 data gate: Baseball Savant is unavailable for this hitter. xBA and Statcast plate-discipline fields stay blank instead of being fabricated.")
    elif d.get("zone_contact_pct") is None or d.get("whiff_pct") is None:
        st.info("Step 2 data note: Savant fallback supplied partial expected/contact-quality data, but some plate-discipline fields are pending.")
    if not d.get("foundation_ready"):
        st.info("Step 2 can describe player skill, but downstream game probability remains gated by Step 1 lineup/starter readiness.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-2 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Step 1 plus Step 2 hitter skill profile • later steps will accumulate here.")
        step1._render_step1(games_df)
        _render_step2(games_df)

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(LEGACY_AUDIT_LABEL, expanded=False):
            st.caption("Frozen V1 calculations remain available here while V2 is rebuilt step-by-step.")
            frozen_detail.render_player_layer(
                games_df,
                section_header,
                status_info,
                team_logo,
                h,
            )
    finally:
        st.caption = original_caption

    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "LEGACY_AUDIT_LABEL",
    "PROBABILITY_IMPACT",
    "STEP2_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_profile",
    "render_player_layer",
]
