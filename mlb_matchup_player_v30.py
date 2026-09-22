"""MLB Matchup Explorer V2 — Steps 1-7 player intelligence stack.

Step 7 adds park, official game-feed weather/roof and opponent fielding context.
It remains descriptive only: frozen V1 Matchup, Daily Top 5, Moneyline, game-level
hit probability, fair odds, simulation and calibration remain untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_environment_v1 as environment
import mlb_matchup_hub_v10 as ui
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4
import mlb_matchup_player_v28 as step5
import mlb_matchup_player_v29 as step6

VERSION = "MLB Matchup Intelligence V2 Step 7"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP7_ROLE = "PARK_WEATHER_DEFENSE_CONTEXT_ONLY"


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


def _fmt_num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _build_step7(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    game_pk = foundation.get("game_pk")
    season = foundation.get("season")
    side = foundation.get("side")
    if not game_pk or not season:
        return environment.build_environment_profile(foundation, None)
    payload = environment.fetch_environment_inputs(int(game_pk), int(season), str(side or ""))
    return environment.build_environment_profile(foundation, payload)


def _render_step7(games_df) -> None:
    d = _build_step7(games_df)
    if not d:
        st.warning("Step 7 park/weather/defense context is waiting for a verified game and player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("environment_data_components") or {}).items()
    )
    score = d.get("environment_score")
    score_text = f"{int(score)}/100" if score is not None else "—"
    temp_text = f"{_fmt_num(d.get('temperature'),0)}°F" if d.get("temperature") is not None else "—"
    park_text = _fmt_num(d.get("park_factor_proxy"), 3)
    defense_games = int(d.get("defense_games") or 0)
    dims = str(d.get("dimension_summary") or "—")

    st.markdown(
        f'''<div class="mxv2-step mxv2-step7">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 7 • PARK + WEATHER + DEFENSE</div>
            <div class="mxv2-badge">{_esc(d.get('environment_data_label'))} • {int(d.get('environment_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> at <b>{_esc(d.get('venue_name_step7'))}</b> • external context around the batted ball</div>
          <div class="mxv2-status">Environment/fielding context only • probability impact: NONE • no bullpen/opportunity/final-probability adjustment yet</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Environment index</span><b>{score_text}</b></div>
            <div class="mxv2-mini"><span>Evidence coverage</span><b>{_fmt_rate(d.get('environment_coverage'))}</b></div>
            <div class="mxv2-mini"><span>Park hit proxy</span><b>{park_text}</b></div>
            <div class="mxv2-mini"><span>Park reliability</span><b>{_fmt_rate(d.get('park_reliability'))}</b></div>
            <div class="mxv2-mini"><span>Temperature</span><b>{temp_text}</b></div>
            <div class="mxv2-mini"><span>Wind</span><b>{_esc(d.get('wind_text'))}</b></div>
            <div class="mxv2-mini"><span>Roof</span><b>{_esc(d.get('roof_type'))}</b></div>
            <div class="mxv2-mini"><span>Fielding%</span><b>{_fmt_avg(d.get('defense_fielding_pct'))}</b></div>
            <div class="mxv2-mini"><span>Errors / game</span><b>{_fmt_num(d.get('defense_errors_per_game'),2)}</b></div>
            <div class="mxv2-mini"><span>Field surface</span><b>{_esc(d.get('turf_type'))}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Environment verdict</b> • {_esc(d.get('environment_label'))} • {score_text} • evidence coverage {_fmt_rate(d.get('environment_coverage'))} • descriptive context, not a hit probability.</div>
          <div class="mxv2-row"><b>Park hit environment</b> • {_esc(d.get('park_label'))} • proxy {park_text} • home AVG {_fmt_avg(d.get('park_home_avg'))} over {int(d.get('park_home_ab') or 0)} AB vs road AVG {_fmt_avg(d.get('park_away_avg'))} over {int(d.get('park_away_ab') or 0)} AB • reliability {_fmt_rate(d.get('park_reliability'))}.</div>
          <div class="mxv2-row"><b>Official weather</b> • {_esc(d.get('weather_label'))} • {temp_text} • {_esc(d.get('condition'))} • wind {_esc(d.get('wind_text'))} • roof {_esc(d.get('roof_type'))}{' • outdoor weather signal suppressed' if d.get('weather_indoor') else ''}.</div>
          <div class="mxv2-row"><b>Opponent fielding</b> • {_esc(d.get('defense_label'))} • fielding {_fmt_avg(d.get('defense_fielding_pct'))} • {int(d.get('defense_errors') or 0)} errors in {defense_games} games • {_fmt_num(d.get('defense_errors_per_game'),2)} errors/game • reliability {_fmt_rate(d.get('defense_reliability'))}.</div>
          <div class="mxv2-row"><b>Field dimensions</b> • {_esc(dims)} • dimensions are displayed only when supplied by the MLB venue feed; missing walls are not guessed.</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Park methodology</b> • {_esc(d.get('park_source'))} • minimum split sample {environment.PARK_MIN_SPLIT_AB} AB • full split reliability at {environment.PARK_FULL_SPLIT_AB} AB.</div>
          <div class="mxv2-row mxv2-muted"><b>Sources</b> • {_esc(d.get('weather_source'))} • {_esc(d.get('defense_source'))}</div>
          <div class="mxv2-row mxv2-muted"><b>Data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 7 measures venue/weather/fielding context only. Step 8 handles bullpen quality; later steps handle PA opportunity and final probability.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if d.get("temperature") is None and not d.get("weather_indoor"):
        st.info("Step 7 weather gate: official temperature is not available in the MLB game feed, so no temperature signal is invented.")
    if str(d.get("wind_direction") or "UNKNOWN") == "UNKNOWN" and not d.get("weather_indoor"):
        st.info("Step 7 weather gate: official wind direction is unresolved, so wind stays neutral/pending rather than being guessed.")
    if d.get("park_factor_proxy") is None:
        st.info(f"Step 7 park gate: the home/road split has not reached the minimum {environment.PARK_MIN_SPLIT_AB}-AB sample on both sides, or the feed is unavailable.")
    if d.get("defense_fielding_pct") is None:
        st.info("Step 7 defense gate: opponent season fielding data is unavailable, so no defensive-strength signal is invented.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-7 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-6 plus Step 7 park/weather/defense context • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        step5._render_step5(games_df)
        step6._render_step6(games_df)
        _render_step7(games_df)

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
    "STEP7_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step7",
    "render_player_layer",
]
