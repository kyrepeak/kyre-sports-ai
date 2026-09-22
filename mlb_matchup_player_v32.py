"""MLB Matchup Explorer V2 — Steps 1-9 player intelligence stack.

Step 9 adds batting-slot plate-appearance opportunity, team PA volume, home/away
history, recent opportunity trend, empirical PA/AB ranges and nominal starter/bullpen
PA exposure. It remains opportunity-only: final hit probability, fair odds, simulation,
calibration and rankings remain untouched until later certified steps.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_opportunity_v1 as opportunity
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4
import mlb_matchup_player_v28 as step5
import mlb_matchup_player_v29 as step6
import mlb_matchup_player_v30 as step7
import mlb_matchup_player_v31 as step8

VERSION = "MLB Matchup Intelligence V2 Step 9"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP9_ROLE = "PLATE_APPEARANCE_OPPORTUNITY_ONLY"


def _esc(value: Any) -> str:
    return ui._esc(value)


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _fmt_range(low: Any, high: Any, digits: int = 1) -> str:
    try:
        return f"{float(low):.{digits}f}–{float(high):.{digits}f}"
    except Exception:
        return "—"


def _build_step9(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    team_id = opportunity.resolve_batting_team_id(games_df, foundation)
    season = foundation.get("season")
    bullpen_profile = step8._build_step8(games_df)
    if not team_id or not season:
        return opportunity.build_opportunity_profile(foundation, team_id, None, None, bullpen_profile)
    season_payload = opportunity.fetch_team_hitting_season(int(team_id), int(season))
    log_payload = opportunity.fetch_team_hitting_logs(int(team_id), int(season))
    return opportunity.build_opportunity_profile(
        foundation,
        int(team_id),
        season_payload,
        log_payload,
        bullpen_profile,
    )


def _render_step9(games_df) -> None:
    d = _build_step9(games_df)
    if not d:
        st.warning("Step 9 plate-appearance opportunity is waiting for a verified game and player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("opportunity_data_components") or {}).items()
    )
    pa_range = _fmt_range(d.get("pa_low"), d.get("pa_high"), 1)
    ab_range = _fmt_range(d.get("ab_low"), d.get("ab_high"), 1)
    slot_text = f"#{int(d.get('slot') or 0)}" if d.get("valid_slot") else "—"
    location = "HOME" if str(d.get("side") or "").lower() == "home" else "AWAY"
    volume_basis = ", ".join(str(x) for x in (d.get("volume_basis") or [])) or "pending"
    slot_basis = ", ".join(str(x) for x in (d.get("slot_basis") or [])) or "pending"

    st.markdown(
        f'''<div class="mxv2-step mxv2-step9">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 9 • PLATE APPEARANCE OPPORTUNITY</div>
            <div class="mxv2-badge">{_esc(d.get('opportunity_data_label'))} • {int(d.get('opportunity_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> • batting {slot_text} • {location} • projected trips to the plate</div>
          <div class="mxv2-status">Opportunity only • {_esc(d.get('opportunity_readiness'))} • probability impact: NONE • Step 11 remains the first game-level hit-probability engine</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Expected PA</span><b>{_fmt(d.get('expected_pa'),2)}</b></div>
            <div class="mxv2-mini"><span>Empirical PA range</span><b>{pa_range}</b></div>
            <div class="mxv2-mini"><span>Expected AB</span><b>{_fmt(d.get('expected_ab'),2)}</b></div>
            <div class="mxv2-mini"><span>Empirical AB range</span><b>{ab_range}</b></div>
            <div class="mxv2-mini"><span>Expected team PA</span><b>{_fmt(d.get('expected_team_pa'),1)}</b></div>
            <div class="mxv2-mini"><span>Season team PA/G</span><b>{_fmt(d.get('season_team_pa_per_game'),1)}</b></div>
            <div class="mxv2-mini"><span>{location} PA/G</span><b>{_fmt(d.get('location_team_pa_per_game'),1)}</b></div>
            <div class="mxv2-mini"><span>Recent-10 PA/G</span><b>{_fmt(d.get('recent_team_pa_per_game'),1)}</b></div>
            <div class="mxv2-mini"><span>Nominal starter PA</span><b>{_fmt(d.get('nominal_starter_pa'),2)}</b></div>
            <div class="mxv2-mini"><span>Nominal bullpen PA</span><b>{_fmt(d.get('nominal_bullpen_pa'),2)}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Opportunity verdict</b> • {_esc(d.get('opportunity_readiness'))} • expected {_fmt(d.get('expected_pa'),2)} PA and {_fmt(d.get('expected_ab'),2)} AB • empirical PA range {pa_range} from {int(d.get('range_sample_games') or 0)} comparable team games.</div>
          <div class="mxv2-row"><b>Team offensive volume</b> • {_esc(d.get('offense_volume_label'))} • season {_fmt(d.get('season_team_pa_per_game'),1)} PA/G • {location.lower()} {_fmt(d.get('location_team_pa_per_game'),1)} over {int(d.get('location_games') or 0)} games • recent-10 {_fmt(d.get('recent_team_pa_per_game'),1)}.</div>
          <div class="mxv2-row"><b>Batting-order mechanics</b> • slot {slot_text} is derived from nine-man lineup cycles using actual team PA totals; top-of-order slots receive the leftover PAs first after each complete lineup cycle.</div>
          <div class="mxv2-row"><b>Starter → bullpen opportunity</b> • nominal starter {_fmt(d.get('nominal_starter_pa'),2)} PA • bullpen {_fmt(d.get('nominal_bullpen_pa'),2)} PA • Step 8 bullpen inning share {_fmt((d.get('bullpen_inning_share_step9') or 0)*100,1) if d.get('bullpen_inning_share_step9') is not None else '—'}% • exposure is approximate context, not opponent-specific PA sequencing.</div>
          <div class="mxv2-row"><b>Ninth-inning handling</b> • {_esc(d.get('ninth_inning_note'))}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>PA-volume blend</b> • season 55% • location 25% when ≥{opportunity.LOCATION_MIN_GAMES} games • recent {opportunity.RECENT_GAMES} 20% when ≥{opportunity.RECENT_MIN_GAMES} games • available weights renormalize rather than filling missing data with guesses.</div>
          <div class="mxv2-row mxv2-muted"><b>AB conversion</b> • hitter season AB/PA {_fmt(d.get('ab_per_pa'),3)} • requires ≥{opportunity.MIN_HITTER_PA_FOR_AB_RATIO} hitter PA; otherwise expected AB stays blank.</div>
          <div class="mxv2-row mxv2-muted"><b>Evidence used</b> • team-volume basis: {_esc(volume_basis)} • slot basis: {_esc(slot_basis)} • range requires ≥{opportunity.RANGE_MIN_GAMES} usable team games.</div>
          <div class="mxv2-row mxv2-muted"><b>Sources</b> • {_esc(d.get('team_season_source'))} • {_esc(d.get('team_logs_source'))}</div>
          <div class="mxv2-row mxv2-muted"><b>Data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 9 estimates opportunity only. Step 10 adds recent-form stability; Step 11 combines the certified inputs into the first V2 hit-probability engine.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if not d.get("valid_slot"):
        st.info("Step 9 gate: no valid batting-order slot is available, so expected PA/AB remain blank instead of being manufactured.")
    elif d.get("opportunity_readiness") == "PROVISIONAL":
        st.info("Step 9 lineup gate: the batting order is projected, not confirmed. Opportunity is shown as provisional and later uncertainty must preserve that status.")
    if d.get("expected_pa") is None:
        st.info("Step 9 team-volume gate: verified team PA evidence is incomplete, so no plate-appearance estimate is invented.")
    if d.get("pa_low") is None or d.get("pa_high") is None:
        st.info(f"Step 9 range gate: at least {opportunity.RANGE_MIN_GAMES} usable team games are required before an empirical PA range is displayed.")
    if d.get("expected_ab") is None:
        st.info(f"Step 9 AB gate: at least {opportunity.MIN_HITTER_PA_FOR_AB_RATIO} hitter season PA are required for a player-specific AB/PA conversion.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-9 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-8 plus Step 9 plate-appearance opportunity • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        step5._render_step5(games_df)
        step6._render_step6(games_df)
        step7._render_step7(games_df)
        step8._render_step8(games_df)
        _render_step9(games_df)

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
    "STEP9_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step9",
    "render_player_layer",
]
