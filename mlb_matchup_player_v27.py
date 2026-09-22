"""MLB Matchup Explorer V2 — Steps 1-4 player intelligence stack.

Step 4 connects hitter and starter through handedness splits and current-season
BvP evidence with explicit sample shrinkage. It remains context-only: the frozen
V1 Matchup model, Daily Top 5, Moneyline and game-level probability math remain
untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_platoon_bvp_v1 as platoon_bvp
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3

VERSION = "MLB Matchup Intelligence V2 Step 4"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP4_ROLE = "PLATOON_BVP_CONTEXT_ONLY"


def _esc(value: Any) -> str:
    return ui._esc(value)


def _fmt_avg(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "—"


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _fmt_num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _build_step4(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None

    step2_data = step2._build_profile(games_df)
    neutral_hit_skill = (step2_data or {}).get("neutral_hit_skill")
    hand_info = platoon_bvp.resolve_handedness(
        foundation.get("starter_hand"),
        foundation.get("batter_hand"),
    )

    hitter_split = {"status": "PENDING", "stat": {}, "source": "MLB Stats API statSplits"}
    pitcher_split = {"status": "PENDING", "stat": {}, "source": "MLB Stats API statSplits"}
    bvp = {"status": "PENDING", "stat": {}, "source": "MLB Stats API vsPlayer"}

    player_id = foundation.get("player_id")
    starter_id = foundation.get("starter_id")
    season = foundation.get("season")
    hitter_code = hand_info.get("hitter_split_code")
    pitcher_code = hand_info.get("pitcher_split_code")

    if player_id and season and hitter_code:
        hitter_split = platoon_bvp.fetch_stat_split(
            int(player_id), int(season), "hitting", str(hitter_code)
        )
    if starter_id and season and pitcher_code:
        pitcher_split = platoon_bvp.fetch_stat_split(
            int(starter_id), int(season), "pitching", str(pitcher_code)
        )
    if player_id and starter_id and season:
        bvp = platoon_bvp.fetch_bvp(int(player_id), int(starter_id), int(season))

    return platoon_bvp.build_platoon_bvp_profile(
        foundation,
        hitter_split,
        pitcher_split,
        bvp,
        neutral_hit_skill,
    )


def _render_step4(games_df) -> None:
    d = _build_step4(games_df)
    if not d:
        st.warning("Step 4 platoon/BvP context is waiting for a verified game and player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("matchup_data_components") or {}).items()
    )
    context_score = d.get("platoon_context_score")
    context_score_text = f"{int(context_score)}/100" if context_score is not None else "—"
    coverage_text = _fmt_rate(d.get("platoon_context_coverage"))
    hitter_label = d.get("hitter_split_label") or "UNKNOWN"
    pitcher_label = d.get("pitcher_split_label") or "UNKNOWN"
    effective_hand = d.get("effective_batter_hand") or "—"
    bvp_ab = int(d.get("bvp_ab") or 0)
    bvp_hits = int(d.get("bvp_hits") or 0)
    bvp_history = (
        f"{bvp_hits}/{bvp_ab} • AVG {_fmt_avg(d.get('bvp_avg'))}"
        if bvp_ab > 0
        else "No current-season BvP history"
    )
    switch_text = (
        f"switch hitter resolves to {effective_hand}HB vs this starter"
        if d.get("switch_adjusted")
        else f"effective batting side {effective_hand}HB"
    )

    st.markdown(
        f'''<div class="mxv2-step mxv2-step4">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 4 • PLATOON + BATTER-VS-PITCHER</div>
            <div class="mxv2-badge">{_esc(d.get('matchup_data_label'))} • {int(d.get('matchup_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> vs <b>{_esc(d.get('starter_name'))}</b> • handedness bridge + sample-shrunk BvP</div>
          <div class="mxv2-status">Pair-specific context only • probability impact: NONE • BvP can inform but cannot overpower the larger sample</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Hitter vs {hitter_label} AVG</span><b>{_fmt_avg(d.get('hitter_split_avg'))}</b></div>
            <div class="mxv2-mini"><span>Hitter vs {hitter_label} OPS</span><b>{_fmt_num(d.get('hitter_split_ops'),3)}</b></div>
            <div class="mxv2-mini"><span>Hitter split AB</span><b>{int(d.get('hitter_split_ab') or 0)}</b></div>
            <div class="mxv2-mini"><span>Hitter split K%</span><b>{_fmt_rate(d.get('hitter_split_k_pct'))}</b></div>
            <div class="mxv2-mini"><span>Pitcher vs {pitcher_label} AVG</span><b>{_fmt_avg(d.get('pitcher_split_avg'))}</b></div>
            <div class="mxv2-mini"><span>Pitcher vs {pitcher_label} OPS</span><b>{_fmt_num(d.get('pitcher_split_ops'),3)}</b></div>
            <div class="mxv2-mini"><span>Pitcher split BF</span><b>{int(d.get('pitcher_split_bf') or 0)}</b></div>
            <div class="mxv2-mini"><span>Pitcher split K%</span><b>{_fmt_rate(d.get('pitcher_split_k_pct'))}</b></div>
            <div class="mxv2-mini"><span>BvP raw AVG</span><b>{_fmt_avg(d.get('bvp_avg'))}</b></div>
            <div class="mxv2-mini"><span>BvP shrunk AVG</span><b>{_fmt_avg(d.get('bvp_shrunk_avg'))}</b></div>
            <div class="mxv2-mini"><span>BvP reliability</span><b>{_fmt_rate(d.get('bvp_reliability'))}</b></div>
            <div class="mxv2-mini"><span>Context index</span><b>{context_score_text}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Handedness bridge</b> • batter {_esc(d.get('batter_hand') or '—')} • starter {_esc(d.get('starter_hand') or '—')} • {_esc(switch_text)} • hitter split vs {_esc(hitter_label)} / pitcher split vs {_esc(pitcher_label)}</div>
          <div class="mxv2-row"><b>Hitter platoon</b> • {int(d.get('hitter_split_hits') or 0)} H / {int(d.get('hitter_split_ab') or 0)} AB • AVG {_fmt_avg(d.get('hitter_split_avg'))} • OPS {_fmt_num(d.get('hitter_split_ops'),3)} • K% {_fmt_rate(d.get('hitter_split_k_pct'))} • BB% {_fmt_rate(d.get('hitter_split_bb_pct'))}</div>
          <div class="mxv2-row"><b>Pitcher vs batter side</b> • {int(d.get('pitcher_split_hits') or 0)} H allowed / {int(d.get('pitcher_split_bf') or 0)} BF • AVG {_fmt_avg(d.get('pitcher_split_avg'))} • OPS {_fmt_num(d.get('pitcher_split_ops'),3)} • K% {_fmt_rate(d.get('pitcher_split_k_pct'))} • BB% {_fmt_rate(d.get('pitcher_split_bb_pct'))}</div>
          <div class="mxv2-row"><b>Current-season BvP</b> • {_esc(bvp_history)} • HR {int(d.get('bvp_home_runs') or 0)} • K {int(d.get('bvp_strikeouts') or 0)} • OPS {_fmt_num(d.get('bvp_ops'),3)}</div>
          <div class="mxv2-row"><b>BvP shrinkage</b> • raw AVG {_fmt_avg(d.get('bvp_avg'))} → shrunk AVG {_fmt_avg(d.get('bvp_shrunk_avg'))} toward matchup baseline {_fmt_avg(d.get('bvp_baseline_avg'))} • reliability {_fmt_rate(d.get('bvp_reliability'))} • prior strength {int(platoon_bvp.BVP_PRIOR_AB)} AB</div>
          <div class="mxv2-row"><b>Platoon/BvP context index</b> • {_esc(d.get('platoon_context_label'))} • {context_score_text} • effective evidence weight {coverage_text} • descriptive only, not a 1+ hit probability.</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Matchup data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 4 links hitter handedness, pitcher batter-side splits and BvP only. Step 5 will add pitch-mix matchup; later steps handle batted-ball quality, environment, bullpen, opportunity and final probability.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if d.get("hitter_split_status") == "PENDING" or d.get("pitcher_split_status") == "PENDING":
        st.info("Step 4 data note: one or more handedness split feeds are pending. Missing split evidence receives zero weight rather than a guessed value.")
    if d.get("bvp_status") == "VERIFIED_NO_HISTORY":
        st.info("Step 4 BvP note: these players have no current-season BvP history. That is treated as zero BvP evidence, not as a positive or negative signal.")
    elif d.get("bvp_status") == "PENDING":
        st.info("Step 4 BvP note: BvP feed is pending. No BvP signal is assumed.")
    elif 0 < bvp_ab < 10:
        st.info(f"Step 4 sample gate: BvP is only {bvp_ab} AB, so it is heavily shrunk toward the matchup baseline and receives very little effective weight.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-4 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-3 plus Step 4 platoon/BvP context • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        _render_step4(games_df)

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
    "STEP4_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step4",
    "render_player_layer",
]
