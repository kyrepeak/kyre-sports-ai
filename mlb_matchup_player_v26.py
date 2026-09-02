"""MLB Matchup Explorer V2 — Steps 1-3 player intelligence stack.

Step 3 adds opposing starting-pitcher quality on top of the certified Step 1 and
Step 2 cards. It is context-only: the frozen V1 Matchup model, Daily Top 5,
Moneyline, final hit probability, fair odds, simulation and calibration remain
untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_pitcher_profile_v1 as pitcher_profile
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2

VERSION = "MLB Matchup Intelligence V2 Step 3"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP3_ROLE = "STARTER_QUALITY_CONTEXT_ONLY"


def _esc(value: Any) -> str:
    return ui._esc(value)


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


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


def _delta(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:+.2f}"
    except Exception:
        return "—"


def _build_step3(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    starter_id = foundation.get("starter_id")
    season = foundation.get("season")
    if not starter_id or not season:
        return pitcher_profile.build_pitcher_profile(foundation, {}, [], None, None, None)

    season_stat = pitcher_profile.fetch_pitcher_season(int(starter_id), int(season))
    logs = pitcher_profile.fetch_pitcher_logs(int(starter_id), int(season))
    savant = pitcher_profile.fetch_savant_expected(int(starter_id), int(season))
    fip_constant = pitcher_profile.fetch_league_fip_constant(int(season))
    tto = pitcher_profile.fetch_tto_profile(int(starter_id), int(season))
    return pitcher_profile.build_pitcher_profile(
        foundation,
        season_stat,
        logs,
        savant,
        fip_constant,
        tto,
    )


def _render_step3(games_df) -> None:
    d = _build_step3(games_df)
    if not d:
        st.warning("Step 3 starter profile is waiting for a verified game and player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("starter_profile_components") or {}).items()
    )
    strength_score = d.get("starter_strength_score")
    strength_text = f"{int(strength_score)}/100" if strength_score is not None else "—"
    strength_coverage = _fmt_rate(d.get("starter_strength_coverage"))
    r5 = d.get("recent5") or {}
    r10 = d.get("recent10") or {}
    tto = d.get("tto") or {}
    tto_segments = tto.get("segments") or {}
    first = tto_segments.get("1st") or {}
    second = tto_segments.get("2nd") or {}
    third = tto_segments.get("3rd+") or {}

    st.markdown(
        f'''<div class="mxv2-step mxv2-step3">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 3 • STARTING PITCHER QUALITY</div>
            <div class="mxv2-badge">{_esc(d.get('starter_profile_label'))} • {int(d.get('starter_profile_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('starter_name'))}</b> ({_esc(d.get('starter_hand'))}) • opposing starter context for {_esc(d.get('player_name'))}</div>
          <div class="mxv2-status">Starter quality only • probability impact: NONE • no platoon/BvP/pitch-mix/game-PA adjustment yet</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>ERA</span><b>{_fmt(d.get('era'))}</b></div>
            <div class="mxv2-mini"><span>xERA</span><b>{_fmt(d.get('xera'))}</b></div>
            <div class="mxv2-mini"><span>FIP</span><b>{_fmt(d.get('fip'))}</b></div>
            <div class="mxv2-mini"><span>WHIP</span><b>{_fmt(d.get('whip'))}</b></div>
            <div class="mxv2-mini"><span>H / 9</span><b>{_fmt(d.get('h9'))}</b></div>
            <div class="mxv2-mini"><span>K%</span><b>{_fmt_rate(d.get('k_pct'))}</b></div>
            <div class="mxv2-mini"><span>BB%</span><b>{_fmt_rate(d.get('bb_pct'))}</b></div>
            <div class="mxv2-mini"><span>xBA allowed</span><b>{_fmt_avg(d.get('xba_allowed'))}</b></div>
            <div class="mxv2-mini"><span>Starter index</span><b>{strength_text}</b></div>
            <div class="mxv2-mini"><span>Index coverage</span><b>{strength_coverage}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Starter quality index</b> • {_esc(d.get('starter_strength_label'))} • {strength_text} • descriptive skill index only, not a hitter probability.</div>
          <div class="mxv2-row"><b>ERA vs xERA</b> • gap {_delta(d.get('era_xera_gap'))} runs • positive means actual ERA is above Statcast xERA; negative means actual ERA is below xERA.</div>
          <div class="mxv2-row"><b>Recent L5</b> • {int(r5.get('starts') or 0)} starts • ERA {_fmt(r5.get('era'))} • WHIP {_fmt(r5.get('whip'))} • H/9 {_fmt(r5.get('h9'))} • K% {_fmt_rate(r5.get('k_pct'))} • BB% {_fmt_rate(r5.get('bb_pct'))}</div>
          <div class="mxv2-row"><b>Recent L10</b> • {int(r10.get('starts') or 0)} starts • ERA {_fmt(r10.get('era'))} • WHIP {_fmt(r10.get('whip'))} • H/9 {_fmt(r10.get('h9'))} • K% {_fmt_rate(r10.get('k_pct'))} • BB% {_fmt_rate(r10.get('bb_pct'))}</div>
          <div class="mxv2-row"><b>Workload</b> • {int(d.get('starter_games_started') or 0)} GS • {_fmt(d.get('starter_innings'),1)} IP • {_fmt(d.get('ip_per_start'),1)} IP/start • {_fmt(d.get('pitches_per_start'),1)} pitches/start • L5 {_fmt(d.get('recent_pitches_per_start'),1)} pitches/start</div>
          <div class="mxv2-row"><b>Times through order</b> • 1st: {int(first.get('bf') or 0)} BF / AVG {_fmt_avg(first.get('avg'))} • 2nd: {int(second.get('bf') or 0)} BF / AVG {_fmt_avg(second.get('avg'))} • 3rd+: {int(third.get('bf') or 0)} BF / AVG {_fmt_avg(third.get('avg'))} • {_esc(d.get('third_time_label'))}</div>
          <div class="mxv2-row"><b>Third-time AVG change</b> • {_delta(d.get('third_time_avg_delta'))} vs first trip when both samples clear the minimum gate.</div>
          <div class="mxv2-row"><b>Expected-stat source</b> • {_esc(d.get('savant_source'))} • {int(d.get('savant_pa') or 0)} PA • {int(d.get('savant_bip') or 0)} BIP</div>
          <div class="mxv2-row"><b>FIP constant</b> • {_fmt(d.get('fip_constant'),3)} • {_esc(d.get('fip_constant_source'))}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Profile completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 3 measures the starter only. Step 4 will combine hitter handedness/platoon and BvP context; later steps handle pitch mix, park, bullpen, opportunity and final probability.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if not d.get("starter_id"):
        st.warning("Step 3 gate: opposing starter identity is missing, so starter-specific quality remains pending.")
        return
    if str(d.get("savant_source")) == "UNAVAILABLE":
        st.info("Step 3 data note: Baseball Savant expected statistics are unavailable for this starter. xERA/xBA allowed stay blank rather than being fabricated.")
    if d.get("fip") is None:
        st.info("Step 3 data note: a current-season league FIP constant was not available, so FIP stays blank rather than using a guessed constant.")
    if tto.get("status") != "VERIFIED":
        st.info("Step 3 data note: times-through-order history is pending; no third-time penalty is assumed.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-3 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-2 plus Step 3 starting-pitcher quality • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        _render_step3(games_df)

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
    "STEP3_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step3",
    "render_player_layer",
]
