"""MLB Matchup Explorer V2 — Steps 1-10 player intelligence stack.

Step 10 adds sample-shrunk L5/L10/L20 recent form, hit-frequency, strikeout and
Statcast contact-quality trends plus a descriptive stability index. It remains
context-only: Step 11 is the first V2 game-level hit-probability engine.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

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
import mlb_matchup_player_v31 as step8
import mlb_matchup_player_v32 as step9
import mlb_matchup_recent_stability_v1 as recent

VERSION = "MLB Matchup Intelligence V2 Step 10"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP10_ROLE = "RECENT_FORM_STABILITY_CONTEXT_ONLY"


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


def _fmt_signed(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):+.{digits}f}"
    except Exception:
        return "—"


def _build_step10(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    player_id = foundation.get("player_id")
    season = foundation.get("season")
    if not player_id or not season:
        return recent.build_recent_stability_profile(foundation, None, None)
    logs = recent.fetch_hitter_game_logs(int(player_id), int(season))
    statcast = recent.fetch_recent_statcast(int(player_id), int(season))
    return recent.build_recent_stability_profile(foundation, logs, statcast)


def _window_row(label: str, row: dict[str, Any]) -> str:
    contact = row.get("contact") or {}
    raw = _fmt_avg(row.get("avg"))
    shrunk = _fmt_avg(row.get("shrunk_avg"))
    return (
        '<div class="mxv2-formrow">'
        f'<div><b>{_esc(label)}</b><span>{int(row.get("games") or 0)} games • {int(row.get("ab") or 0)} AB</span></div>'
        f'<div><b>{raw}</b><span>raw AVG</span></div>'
        f'<div><b>{shrunk}</b><span>shrunk AVG</span></div>'
        f'<div><b>{_fmt_rate(row.get("hit_game_rate"))}</b><span>1+ hit games</span></div>'
        f'<div><b>{_fmt_rate(row.get("k_pct"))}</b><span>K%</span></div>'
        f'<div><b>{_fmt_avg(contact.get("xba_contact"))}</b><span>xBA/contact</span></div>'
        f'<div><b>{_fmt_rate(contact.get("hard_hit_pct"))}</b><span>Hard-Hit%</span></div>'
        f'<div><b>{_fmt_rate(row.get("reliability"))}</b><span>AVG reliability</span></div>'
        '</div>'
    )


def _render_step10(games_df) -> None:
    d = _build_step10(games_df)
    if not d:
        st.warning("Step 10 recent-form stability is waiting for a verified player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("recent_data_components") or {}).items()
    )
    form_score = d.get("recent_form_score")
    stability_score = d.get("stability_score")
    form_text = f"{int(form_score)}/100" if form_score is not None else "—"
    stability_text = f"{int(stability_score)}/100" if stability_score is not None else "—"
    season_contact = d.get("season_contact_step10") or {}
    rows = "".join(
        _window_row(label, d.get(key) or {})
        for label, key in (("L5", "l5"), ("L10", "l10"), ("L20", "l20"))
    )

    st.markdown(
        f'''<div class="mxv2-step mxv2-step10">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 10 • RECENT FORM + STABILITY</div>
            <div class="mxv2-badge">{_esc(d.get('recent_data_label'))} • {int(d.get('recent_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> • L5/L10/L20 pregame form with sample shrinkage</div>
          <div class="mxv2-status">Recent-form context only • {_esc(d.get('recent_readiness'))} • probability impact: NONE • Step 11 combines certified inputs</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Recent-form index</span><b>{form_text}</b></div>
            <div class="mxv2-mini"><span>Form verdict</span><b>{_esc(d.get('recent_form_label'))}</b></div>
            <div class="mxv2-mini"><span>Stability score</span><b>{stability_text}</b></div>
            <div class="mxv2-mini"><span>Stability</span><b>{_esc(d.get('stability_label'))}</b></div>
            <div class="mxv2-mini"><span>Trend</span><b>{_esc(d.get('trend_label'))}</b></div>
            <div class="mxv2-mini"><span>L5 vs L20</span><b>{_fmt_signed(d.get('trend_delta'))}</b></div>
            <div class="mxv2-mini"><span>Season AVG</span><b>{_fmt_avg(d.get('season_avg_step10'))}</b></div>
            <div class="mxv2-mini"><span>Season K%</span><b>{_fmt_rate(d.get('season_k_pct_step10'))}</b></div>
            <div class="mxv2-mini"><span>Season xBA/contact</span><b>{_fmt_avg(season_contact.get('xba_contact'))}</b></div>
            <div class="mxv2-mini"><span>Season Hard-Hit%</span><b>{_fmt_rate(season_contact.get('hard_hit_pct'))}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Recent-form verdict</b> • {_esc(d.get('recent_form_label'))} • {form_text} • evidence coverage {_fmt_rate(d.get('recent_form_coverage'))} • descriptive context, not a hit probability.</div>
          <div class="mxv2-row"><b>Stability verdict</b> • {_esc(d.get('stability_label'))} • {stability_text} • reliability {_fmt_rate(d.get('stability_reliability'))} • shrunk-AVG spread {_fmt(d.get('avg_window_spread'),3)} • K% spread {_fmt_rate(d.get('k_window_spread'))}.</div>
          <div class="mxv2-row"><b>Pregame cutoff</b> • only completed games strictly before {_esc(d.get('recent_asof_date'))} are eligible • {int(d.get('recent_log_games') or 0)} official logs available.</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-formhead">L5 / L10 / L20 • RESULTS + CONTACT TREND</div>
          {rows}
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Sample protection</b> • {_esc(d.get('recent_sample_note'))}</div>
          <div class="mxv2-row mxv2-muted"><b>Window priors</b> • L5 {int(recent.WINDOW_PRIORS[5])} AB • L10 {int(recent.WINDOW_PRIORS[10])} AB • L20 {int(recent.WINDOW_PRIORS[20])} AB • form blend weights L5 20% / L10 35% / L20 45% before reliability scaling.</div>
          <div class="mxv2-row mxv2-muted"><b>Contact trend</b> • recent xBA/contact, EV, Hard-Hit%, contact% and whiff% come from the shared certified Statcast batter feed and are matched to official pregame game IDs.</div>
          <div class="mxv2-row mxv2-muted"><b>Sources</b> • {_esc(d.get('recent_logs_source'))} • {_esc(d.get('recent_statcast_source'))}</div>
          <div class="mxv2-row mxv2-muted"><b>Data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 10 describes recent form and volatility only. Step 11 is the first V2 engine allowed to combine true talent, starter, platoon, pitch mix, contact quality, environment, bullpen, opportunity and recent stability into game-level hit probabilities.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if d.get("recent_logs_status") != "VERIFIED":
        st.info("Step 10 log gate: official hitter game logs are unavailable, so recent-form windows stay pending rather than being invented.")
    if d.get("recent_log_games", 0) < recent.MIN_LOG_GAMES:
        st.info(f"Step 10 sample gate: at least {recent.MIN_LOG_GAMES} completed pregame hitting logs are required before recent form is treated as usable context.")
    if d.get("recent_statcast_status") != "VERIFIED":
        st.info("Step 10 Statcast gate: recent contact-quality trends are unavailable; the model does not backfill EV/xBA/Hard-Hit from guesses.")
    if d.get("stability_label") == "LOW SAMPLE":
        st.info("Step 10 stability gate: the L20 sample is too small for a strong volatility conclusion, so stability remains low-confidence.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-10 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-9 plus Step 10 recent-form stability • Step 11 activates the first V2 probability engine.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        step5._render_step5(games_df)
        step6._render_step6(games_df)
        step7._render_step7(games_df)
        step8._render_step8(games_df)
        step9._render_step9(games_df)
        _render_step10(games_df)

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
    "STEP10_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step10",
    "render_player_layer",
]
