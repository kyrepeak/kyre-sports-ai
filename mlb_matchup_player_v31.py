"""MLB Matchup Explorer V2 — Steps 1-8 player intelligence stack.

Step 8 adds opponent bullpen quality, handedness, recent workload/availability and
nominal post-starter exposure. It remains descriptive only: frozen V1 Matchup,
Daily Top 5, Moneyline, game-level hit probability, fair odds, simulation and
calibration remain untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_bullpen_v1 as bullpen
import mlb_matchup_hub_v10 as ui
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4
import mlb_matchup_player_v28 as step5
import mlb_matchup_player_v29 as step6
import mlb_matchup_player_v30 as step7

VERSION = "MLB Matchup Intelligence V2 Step 8"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP8_ROLE = "BULLPEN_PATH_CONTEXT_ONLY"


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


def _build_step8(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    opponent_team_id = bullpen.resolve_opponent_team_id(games_df, foundation)
    season = foundation.get("season")
    game_date = str(foundation.get("game_date") or "")
    starter_profile = step3._build_step3(games_df)
    if not opponent_team_id or not season:
        return bullpen.build_bullpen_profile(
            foundation,
            opponent_team_id,
            None,
            None,
            None,
            None,
            starter_profile,
        )
    active = bullpen.fetch_active_pitchers(int(opponent_team_id), int(season), game_date)
    season_stats = bullpen.fetch_team_pitcher_stats(int(opponent_team_id), int(season))
    recent = bullpen.fetch_recent_workload(int(opponent_team_id), int(season), game_date)
    savant = bullpen.fetch_savant_expected_table(int(season))
    return bullpen.build_bullpen_profile(
        foundation,
        opponent_team_id,
        active,
        season_stats,
        recent,
        savant,
        starter_profile,
    )


def _reliever_row_html(row: dict[str, Any]) -> str:
    return (
        '<div class="mxv2-bprow">'
        f'<div><b>{_esc(row.get("name"))}</b><span>{_esc(row.get("hand"))}HP • {_fmt(row.get("ip"),1)} IP</span></div>'
        f'<div><b>{_fmt(row.get("era"),2)}</b><span>ERA</span></div>'
        f'<div><b>{_fmt(row.get("xera"),2)}</b><span>xERA</span></div>'
        f'<div><b>{_fmt_rate(row.get("k_pct"))}</b><span>K%</span></div>'
        f'<div><b>{_fmt_rate(row.get("bb_pct"))}</b><span>BB%</span></div>'
        f'<div><b>{int(row.get("day1_pitches") or 0)}</b><span>pitches yesterday</span></div>'
        f'<div><b>{int(row.get("two_day_pitches") or 0)}</b><span>2-day pitches</span></div>'
        f'<div><b>{_esc(row.get("fatigue_status"))}</b><span>{_esc(row.get("fatigue_reason"))}</span></div>'
        '</div>'
    )


def _render_step8(games_df) -> None:
    d = _build_step8(games_df)
    if not d:
        st.warning("Step 8 bullpen path is waiting for a verified game and player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("bullpen_data_components") or {}).items()
    )
    path_score = d.get("bullpen_path_score")
    path_text = f"{int(path_score)}/100" if path_score is not None else "—"
    quality_score = d.get("bullpen_quality_score")
    quality_text = f"{int(quality_score)}/100" if quality_score is not None else "—"
    availability = d.get("availability_index")
    exposure = d.get("exposure") or {}
    reliever_rows = "".join(_reliever_row_html(row) for row in (d.get("relievers") or [])[:8])
    if not reliever_rows:
        reliever_rows = '<div class="mxv2-row mxv2-muted">Active reliever season lines are pending; no bullpen strength is invented.</div>'

    st.markdown(
        f'''<div class="mxv2-step mxv2-step8">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 8 • BULLPEN PATH</div>
            <div class="mxv2-badge">{_esc(d.get('bullpen_data_label'))} • {int(d.get('bullpen_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> vs <b>{_esc(d.get('opponent'))}</b> relief corps • post-starter matchup context</div>
          <div class="mxv2-status">Bullpen context only • probability impact: NONE • nominal inning exposure is not a plate-appearance projection</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Relief-path index</span><b>{path_text}</b></div>
            <div class="mxv2-mini"><span>Pure bullpen quality</span><b>{quality_text}</b></div>
            <div class="mxv2-mini"><span>ERA</span><b>{_fmt(d.get('era'),2)}</b></div>
            <div class="mxv2-mini"><span>xERA</span><b>{_fmt(d.get('xera'),2)}</b></div>
            <div class="mxv2-mini"><span>WHIP</span><b>{_fmt(d.get('whip'),2)}</b></div>
            <div class="mxv2-mini"><span>H/9</span><b>{_fmt(d.get('h9'),2)}</b></div>
            <div class="mxv2-mini"><span>K%</span><b>{_fmt_rate(d.get('k_pct'))}</b></div>
            <div class="mxv2-mini"><span>BB%</span><b>{_fmt_rate(d.get('bb_pct'))}</b></div>
            <div class="mxv2-mini"><span>xBA allowed</span><b>{_fmt_avg(d.get('xba_allowed'))}</b></div>
            <div class="mxv2-mini"><span>Depth availability</span><b>{_fmt_rate(availability)}</b></div>
            <div class="mxv2-mini"><span>Expected bullpen IP</span><b>{_fmt(d.get('expected_bullpen_ip'),1)}</b></div>
            <div class="mxv2-mini"><span>Nominal inning share</span><b>{_fmt_rate(d.get('bullpen_inning_share'))}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Relief-path verdict</b> • {_esc(d.get('bullpen_path_label'))} • {path_text} • availability can move the descriptive path index, but it does not change final hit probability in Step 8.</div>
          <div class="mxv2-row"><b>Season relief quality</b> • {_esc(d.get('bullpen_quality_label'))} • {quality_text} • {int(d.get('reliever_count') or 0)} active relievers • {_fmt(d.get('bullpen_innings'),1)} combined relief IP • expected-stat sample {int(d.get('expected_stats_pa') or 0)} PA.</div>
          <div class="mxv2-row"><b>Handedness mix</b> • LHP {_fmt_rate(d.get('left_share'))} • RHP {_fmt_rate(d.get('right_share'))} • known-hand coverage {_fmt_rate(d.get('hand_coverage'))} by relief IP.</div>
          <div class="mxv2-row"><b>Recent availability</b> • READY {int(d.get('ready_count') or 0)} • WATCH {int(d.get('watch_count') or 0)} • LIMITED {int(d.get('limited_count') or 0)} • UNKNOWN {int(d.get('unknown_count') or 0)} • depth availability {_fmt_rate(availability)}.</div>
          <div class="mxv2-row"><b>Starter → bullpen exposure</b> • expected starter {_fmt(d.get('expected_starter_ip'),1)} IP • expected bullpen {_fmt(d.get('expected_bullpen_ip'),1)} IP • nominal bullpen share {_fmt_rate(d.get('bullpen_inning_share'))} • {_esc(d.get('exposure_basis'))}.</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-bphead">ACTIVE RELIEVER DEPTH • SEASON SKILL + PRIOR-DAY WORKLOAD</div>
          {reliever_rows}
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Availability rules</b> • LIMITED at ≥{bullpen.LIMITED_YESTERDAY_PITCHES} pitches yesterday or ≥{bullpen.LIMITED_TWO_DAY_PITCHES} over two days • WATCH at ≥{bullpen.WATCH_YESTERDAY_PITCHES} yesterday, ≥{bullpen.WATCH_TWO_DAY_PITCHES} over two days, or verified back-to-back use • incomplete workload stays UNKNOWN.</div>
          <div class="mxv2-row mxv2-muted"><b>Reliever classification</b> • starter is excluded • active pitchers qualify as relievers when season starts ≤{bullpen.RELIEVER_MAX_STARTS} or starts/games ≤{int(bullpen.RELIEVER_MAX_START_SHARE*100)}%.</div>
          <div class="mxv2-row mxv2-muted"><b>Sources</b> • {_esc(d.get('active_source'))} • {_esc(d.get('season_source'))} • {_esc(d.get('workload_source'))} • {_esc(d.get('savant_source'))}</div>
          <div class="mxv2-row mxv2-muted"><b>Data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 8 describes bullpen skill, handedness, workload and nominal inning exposure only. Step 9 builds plate-appearance opportunity; Step 11 is the first game-level probability engine.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if not d.get("opponent_team_id_step8"):
        st.info("Step 8 gate: opponent team identity could not be resolved from the verified game row, so bullpen context stays pending.")
    if d.get("active_roster_status") != "VERIFIED" or d.get("season_pitching_status") != "VERIFIED":
        st.info("Step 8 bullpen gate: active roster or season pitching lines are incomplete, so missing relief skill is not fabricated.")
    if d.get("workload_status") != "VERIFIED":
        st.info("Step 8 workload gate: recent pitcher usage is incomplete. Availability remains UNKNOWN where needed rather than assuming every reliever is rested.")
    if d.get("savant_status") != "VERIFIED":
        st.info("Step 8 expected-stat gate: Baseball Savant relief xERA/xBA is unavailable, so those fields stay blank.")
    if exposure.get("status") != "VERIFIED":
        st.info("Step 8 exposure gate: starter workload is incomplete, so expected bullpen innings are not guessed.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-8 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-7 plus Step 8 bullpen path • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        step5._render_step5(games_df)
        step6._render_step6(games_df)
        step7._render_step7(games_df)
        _render_step8(games_df)

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(LEGACY_AUDIT_LABEL, expanded=False):
            st.caption("Frozen V1 calculations remain available here while V2 is rebuilt step-by-step.")
            frozen_detail.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption

    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "LEGACY_AUDIT_LABEL",
    "PROBABILITY_IMPACT",
    "STEP8_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step8",
    "render_player_layer",
]
