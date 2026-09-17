"""CFB Game Total Clean Page V8 — Hit-style connected final flow.

Presentation-only wrapper over frozen V7. V8 keeps the certified Game Total
analysis path intact while presenting the main evidence in one continuous order:
Steps 1–10 -> Step 11 Distribution -> Step 12 Final -> Top-5.

Frozen Game Total analysis, qualification, distribution, final math, ranking,
and sportsbook influence remain unchanged. Raw/deep evidence is moved below the
main flow into collapsed drawers so it no longer interrupts the scan path.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v7 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V8 • V157 HIT-STYLE COMBINED FLOW"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v7"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
COMBINED_FLOW_ORDER = (
    "Steps 1–10",
    "Step 11 Distribution",
    "Step 12 Final",
    "Top-5",
)

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display
base = prior.prior  # frozen V6 display/model bridge

_V157_CSS = r"""
<style>
.gt157-flowhead{margin:2px 0 7px;padding:8px 9px;border-radius:11px;background:linear-gradient(145deg,rgba(76,45,126,.16),rgba(9,23,34,.92));border:1px solid rgba(189,152,255,.18)}
.gt157-flowhead b{display:block;color:#e7dbff;font-size:.49rem;font-weight:950;letter-spacing:.08em}.gt157-flowhead span{display:block;color:var(--gt-gray);font-size:.27rem;line-height:1.4;margin-top:3px}
.gt157-model{margin:8px 0 2px;padding-top:7px;border-top:1px solid rgba(121,146,169,.12)}
.gt157-model-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt157-model-head b{color:#edf4fa;font-size:.50rem;font-weight:950;letter-spacing:.06em}.gt157-model-head span{color:var(--gt-gray);font-size:.27rem}
.gt157-stage{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:8px;align-items:center;min-height:52px;padding:8px 9px;margin-top:5px;border-radius:11px;background:#0a1823;border:1px solid rgba(116,145,170,.15);position:relative;overflow:hidden}
.gt157-stage:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--gt-purple)}.gt157-stage.ready{border-color:rgba(60,207,137,.24);background:linear-gradient(145deg,rgba(17,72,51,.15),#0a1823)}.gt157-stage.gated{border-color:rgba(244,191,77,.23);background:linear-gradient(145deg,rgba(101,72,18,.12),#0a1823)}
.gt157-num{display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:rgba(189,152,255,.11);color:var(--gt-purple);font-size:.40rem;font-weight:950}.gt157-copy{min-width:0}.gt157-copy b{display:block;color:#f4f8fb;font-size:.50rem;font-weight:950}.gt157-copy span{display:block;color:#8396a7;font-size:.28rem;line-height:1.38;margin-top:2px}.gt157-value{display:flex;align-items:center;gap:6px;white-space:nowrap}.gt157-value strong{color:#f5f9fc;font-size:.70rem}.gt157-badge{padding:4px 7px;border-radius:999px;font-size:.27rem;font-weight:950}.gt157-badge.ready{background:rgba(34,197,94,.13);color:var(--gt-green)}.gt157-badge.gated{background:rgba(245,158,11,.13);color:var(--gt-amber)}
.gt157-final{margin:6px 0 2px 38px;border:1px solid rgba(160,112,255,.20);border-radius:10px;background:linear-gradient(145deg,rgba(75,41,127,.15),#0a1723);padding:8px 9px}.gt157-finaltop{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt157-finaltop b{color:#d9c8ff;font-size:.33rem;font-weight:950;letter-spacing:.06em}.gt157-finaltop span{color:var(--gt-purple);font-size:.25rem;font-weight:950}.gt157-finalgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-top:6px}.gt157-metric{background:#102330;border-radius:7px;padding:5px;min-width:0}.gt157-metric b{display:block;color:#edf4f9;font-size:.40rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt157-metric span{display:block;color:var(--gt-gray);font-size:.19rem;font-weight:850;text-transform:uppercase;margin-top:2px}.gt157-note{margin-top:6px;color:#7f91a1;font-size:.23rem;line-height:1.4}.gt157-note strong{color:var(--gt-purple)}
.gt157-top5{margin:9px 0 2px;padding:9px;border-radius:12px;background:#0a1722;border:1px solid rgba(116,145,170,.16)}.gt157-top5head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}.gt157-top5head b{color:#eef5fb;font-size:.50rem;font-weight:950;letter-spacing:.06em}.gt157-top5head span{color:var(--gt-gray);font-size:.27rem}.gt157-deep{margin-top:8px;padding-top:7px;border-top:1px solid rgba(121,146,169,.12);color:var(--gt-gray);font-size:.28rem}
@media(max-width:760px){.gt157-stage{grid-template-columns:28px minmax(0,1fr);align-items:start}.gt157-value{grid-column:2;margin-top:2px}.gt157-final{margin-left:0}.gt157-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt157-finalgrid .gt157-metric:first-child{grid-column:1/-1}.gt157-model-head,.gt157-top5head{align-items:flex-start;flex-direction:column;gap:2px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _model_flow(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    """Re-present frozen Step 11/12 output as two sequential flow stages."""
    step11_ready = bool(raw.get("ready"))
    step12_ready = bool(final.get("ready"))

    step11_reason = (
        "Distribution ready • frozen model output preserved"
        if step11_ready
        else " • ".join(str(x) for x in raw.get("reasons") or ["Distribution inputs incomplete"])
    )
    step12_reason = (
        "Final synthesis ready • frozen qualification preserved"
        if step12_ready
        else " • ".join(str(x) for x in final.get("reasons") or ["Final qualification unavailable"])
    )

    projected = final.get("projected_combined_total") if step12_ready else raw.get("projected_combined_total")
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    grade = _clean(final.get("grade")) if step12_ready else "—"
    strength = _pct(final.get("forecast_strength")) if step12_ready else "—"
    core_text = (
        f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}"
        if step12_ready and core
        else "—"
    )
    band_text = _clean(band.get("label")) if step12_ready else "—"
    final_state = "FINAL READY" if step12_ready else ("DISTRIBUTION READY" if step11_ready else "GATED")

    return f"""
<div class="gt157-model" data-testid="gt157-model-flow">
  <div class="gt157-model-head"><b>🧠 MODEL FLOW</b><span>Step 11 → Step 12 • frozen outputs only</span></div>
  <div class="gt157-stage {'ready' if step11_ready else 'gated'}" data-testid="gt157-step11-card">
    <div class="gt157-num">11</div>
    <div class="gt157-copy"><b>Distribution</b><span>{escape(step11_reason)}</span></div>
    <div class="gt157-value"><strong>{escape(_num(raw.get('projected_combined_total')))}</strong><span class="gt157-badge {'ready' if step11_ready else 'gated'}">{'READY' if step11_ready else 'GATED'}</span></div>
  </div>
  <div class="gt157-stage {'ready' if step12_ready else 'gated'}" data-testid="gt157-step12-card">
    <div class="gt157-num">12</div>
    <div class="gt157-copy"><b>Final Synthesis</b><span>{escape(step12_reason)}</span></div>
    <div class="gt157-value"><strong>{escape(_num(projected))}</strong><span class="gt157-badge {'ready' if step12_ready else 'gated'}">{'READY' if step12_ready else 'GATED'}</span></div>
  </div>
  <div class="gt157-final" data-testid="gt157-final-summary">
    <div class="gt157-finaltop"><b>FINAL • MODEL SUMMARY</b><span>{escape(final_state)}</span></div>
    <div class="gt157-finalgrid">
      <div class="gt157-metric"><b>{escape(_num(projected))}</b><span>Projection</span></div>
      <div class="gt157-metric"><b>{escape(core_text)}</b><span>Core 50%</span></div>
      <div class="gt157-metric"><b>{escape(band_text or '—')}</b><span>Likely band</span></div>
      <div class="gt157-metric"><b>{escape(grade or '—')}</b><span>Grade</span></div>
      <div class="gt157-metric"><b>{escape(strength)}</b><span>Strength</span></div>
    </div>
    <div class="gt157-note"><strong>0.0% sportsbook projection influence.</strong> No projection, qualification, distribution, or ranking math is changed by this presentation.</div>
  </div>
</div>
"""


def _render_top5(games, selected_day: str) -> None:
    st.markdown(
        """
<div class="gt157-top5" data-testid="gt157-top5-stage">
  <div class="gt157-top5head"><b>🏆 TOP-5 • FINAL FLOW</b><span>Frozen Step-12 qualification + ranking</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
    scan_key = f"cfb_v152_top5_{selected_day}"
    diag_key = f"cfb_v152_scan_diag_{selected_day}"
    if st.button(
        "Run final Game Total Top-5 scan",
        type="primary",
        key=f"cfb_v152_scan_button_{selected_day}",
    ):
        with st.spinner("Scanning the verified CFB slate through frozen Steps 11–12..."):
            rows, diag = frozen_page.slate.scan_slate(games, selected_day)
            st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5)
            st.session_state[diag_key] = diag

    top5 = st.session_state.get(scan_key) or []
    diag = st.session_state.get(diag_key) or {}
    if diag:
        st.caption(
            f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • "
            f"{int(diag.get('final_ready') or 0)} final-ready • "
            f"{int(diag.get('qualified_forecasts') or 0)} ranked-eligible • "
            f"{len(diag.get('errors') or [])} errors"
        )
    if top5:
        for row in top5:
            st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
    elif diag:
        st.warning("No game cleared the frozen Step-12 qualification thresholds. V157 will not force a Top-5.")
    else:
        st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")


def _render_deep_evidence(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    game: Mapping[str, Any],
) -> None:
    st.markdown(
        '<div class="gt157-deep" data-testid="gt157-deep-evidence">Deep/raw evidence stays below the decision flow and collapsed by default.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("🔬 Raw Steps 1–10 evidence", expanded=False):
        prior._render_raw_team_evidence(away, home)

    with st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False):
        st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
        for panel in (
            frozen_page.frozen_v2._band_panel(raw),
            frozen_page.frozen_v2._around_projection_panel(raw),
            frozen_page.frozen_v2._exact_panel(raw),
            frozen_page.frozen_v2._components_panel(raw),
        ):
            if panel:
                st.markdown(panel, unsafe_allow_html=True)

    with st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False):
        st.markdown(frozen_page._final_card(game, final), unsafe_allow_html=True)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Render one Hit-style connected UI over the untouched frozen model path."""
    st.markdown(
        base.prior.prior.prior.prior.prior._CSS
        + base.prior.prior.prior.prior._V151_CSS
        + base.prior._V152_EVIDENCE_CSS
        + base._V152_MONSTER_CSS
        + prior._V155_TEAM_CSS
        + _V157_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="gt152-shell">
  <div class="gt152-shelltop">
    <div><div class="gt152-kicker">CFB GAME TOTAL • MONSTER DASHBOARD</div><div class="gt152-title">College Football Game Total</div><div class="gt152-sub">One connected read: matchup → Steps 1–10 → Step 11 → Step 12 → Top-5.</div></div>
    <div class="gt152-live">V157 COMBINED FLOW ✅</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(base.prior.prior.prior.prior.prior._PHOENIX).date(),
        key="cfb_v152_game_total_date",
    )
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V157 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v152_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # FROZEN MODEL PATH: identical source call and untouched selected game.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY-ONLY PATH: reconciled copy never feeds frozen calculations.
    display_game, display_away, display_home, _display_diag = runtime_display.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = base.prior.prior.prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = base.prior.prior._team_stats_state(display_away, display_game, "away")
    home_stats = base.prior.prior._team_stats_state(display_home, display_game, "home")
    away_evidence = base.prior._team_evidence_state(display_away, display_game, "away")
    home_evidence = base.prior._team_evidence_state(display_home, display_game, "home")

    st.markdown(base._monster_matchup_hero(identity, away_stats, home_stats), unsafe_allow_html=True)
    st.markdown(base._compact_game_strip(identity), unsafe_allow_html=True)
    st.markdown(base._scoring_defense_summary(away_stats, home_stats), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
<div class="gt157-flowhead" data-testid="gt157-connected-flow">
  <b>CONNECTED GAME TOTAL FLOW</b>
  <span>Steps 1–10 → Step 11 Distribution → Step 12 Final → Top-5. Deep evidence stays collapsed below, just like the cleaner Hit-page scan path.</span>
</div>
""",
            unsafe_allow_html=True,
        )

        # Stage 1: existing compact Steps 1–10 plus the approved compact team evidence.
        base._render_steps_1_10_rail(identity, away_evidence, home_evidence, display_game)
        prior._render_compact_team_cards(away_evidence, home_evidence)

        # Stages 11–12: same frozen outputs, now sequential instead of detached cards.
        st.markdown(_model_flow(raw, final), unsafe_allow_html=True)

        # Final scan stage: visible immediately after Step 12 instead of buried behind deep drawers.
        _render_top5(games, selected_day)

        # Supporting/raw material follows the main decision flow and stays collapsed.
        _render_deep_evidence(away_evidence, home_evidence, raw, final, game)

    st.caption("🛡️ V157 combined display only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V157 Game Total V8 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "COMBINED_FLOW_ORDER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_model_flow",
    "_render_deep_evidence",
    "_render_top5",
    "render_cfb_hub",
    "render_game_total_hub",
]
