"""CFB Game Total Clean Page V7 — compact team evidence flow.

Presentation-only additive renderer over closed V6. V7 preserves the exact V6
frozen analysis call and display reconciliation, then renders the same V6
presentation helpers with compact team evidence inserted directly between the
Steps 1–10 rail and the single collapsed raw-evidence drawer.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v6 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V7 • V155 COMPACT TEAM EVIDENCE"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v6"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
V155_ACTIVE_MARKER = "CFB_GAME_TOTAL_V155_TEAM_EVIDENCE_ACTIVE"

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display

_V155_TEAM_CSS = r"""
<style>
.gt155-team-flow{margin:8px 0 3px;padding-top:7px;border-top:1px solid rgba(121,146,169,.12)}
.gt155-team-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt155-team-head b{color:#eef5fb;font-size:.50rem;font-weight:950;letter-spacing:.06em}.gt155-team-head span{color:var(--gt-gray);font-size:.27rem}
.gt155-team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt155-team-card{padding:8px 9px;border-radius:11px;background:#0a1823;border:1px solid rgba(116,145,170,.14);min-width:0}.gt155-team-cardhead{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt155-team-name{color:#f4f8fb;font-size:.53rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt155-team-record{padding:3px 6px;border-radius:999px;background:rgba(112,73,176,.17);color:var(--gt-purple);font-size:.27rem;font-weight:950;white-space:nowrap}
.gt155-team-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:6px}.gt155-team-metric{padding:5px;border-radius:7px;background:#102330;min-width:0}.gt155-team-metric b{display:block;color:#edf4f9;font-size:.40rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt155-team-metric span{display:block;color:var(--gt-gray);font-size:.20rem;font-weight:850;text-transform:uppercase;margin-top:2px}.gt155-team-source{margin-top:6px;color:var(--gt-gray);font-size:.24rem;line-height:1.35;overflow-wrap:anywhere}.gt155-team-source strong{color:var(--gt-green)}
@media(max-width:760px){.gt155-team-grid{grid-template-columns:1fr}.gt155-team-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.gt155-team-head{align-items:flex-start;flex-direction:column;gap:2px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _team_card(state: Mapping[str, Any], side: str) -> str:
    team = _clean(state.get("team")) or side.title()
    record = _clean(state.get("record")) or "—"
    source = _clean(state.get("data_source")) or "Completed-game evidence"
    form = _clean(state.get("recent_form")) or "—"
    test_id_attr = 'data-testid="gt155-away-team-card"' if side == "away" else 'data-testid="gt155-home-team-card"'
    return f"""
<div class="gt155-team-card" {test_id_attr}>
  <div class="gt155-team-cardhead">
    <div class="gt155-team-name">{escape(team)}</div>
    <div class="gt155-team-record">{escape(record)}</div>
  </div>
  <div class="gt155-team-metrics">
    <div class="gt155-team-metric"><b>{_num(state.get('ppg'))}</b><span>PPG</span></div>
    <div class="gt155-team-metric"><b>{_num(state.get('allowed_pg'))}</b><span>Allowed</span></div>
    <div class="gt155-team-metric"><b>{_num(state.get('point_diff_pg'))}</b><span>Point diff</span></div>
    <div class="gt155-team-metric"><b>{escape(form)}</b><span>Recent form</span></div>
  </div>
  <div class="gt155-team-source"><strong>DATA</strong> • {escape(source)}</div>
</div>
"""


def _render_compact_team_cards(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    st.markdown(
        f"""
<div class="gt155-team-flow" data-testid="gt155-team-evidence-flow">
  <div class="gt155-team-head"><b>🏈 TEAM EVIDENCE</b><span>Key team facts stay visible • full detail stays collapsed</span></div>
  <div class="gt155-team-grid">{_team_card(away, 'away')}{_team_card(home, 'home')}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_raw_team_evidence(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    """Render both full team bodies inside the one existing raw drawer."""
    away_team = _clean(away.get("team")) or "Away team"
    home_team = _clean(home.get("team")) or "Home team"
    st.markdown(f"**{away_team} • full evidence**")
    prior.prior._render_team_evidence_body(away)
    st.divider()
    st.markdown(f"**{home_team} • full evidence**")
    prior.prior._render_team_evidence_body(home)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Render V155 directly while preserving V6 frozen analysis semantics."""
    v5 = prior.prior
    st.markdown(
        v5.prior.prior.prior.prior._CSS
        + v5.prior.prior.prior._V151_CSS
        + v5._V152_EVIDENCE_CSS
        + prior._V152_MONSTER_CSS
        + _V155_TEAM_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div class="gt152-shell" data-testid="gt155-active">
  <div class="gt152-shelltop">
    <div><div class="gt152-kicker">CFB GAME TOTAL • MONSTER DASHBOARD</div><div class="gt152-title">College Football Game Total</div><div class="gt152-sub">Matchup first. Connected evidence next. Deep model machinery stays out of the way until you want it.</div></div>
    <div class="gt152-live">V155 TEAM FLOW ACTIVE ✅</div>
  </div>
  <span style="display:none">{V155_ACTIVE_MARKER}</span>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(v5.prior.prior.prior.prior._PHOENIX).date(),
        key="cfb_v152_game_total_date",
    )
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V152 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v152_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # FROZEN MODEL PATH: identical V6 call; untouched selected game first.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY-ONLY PATH: identical V6 reconciliation; never feeds frozen math.
    display_game, display_away, display_home, display_diag = runtime_display.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = v5.prior.prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = v5.prior._team_stats_state(display_away, display_game, "away")
    home_stats = v5.prior._team_stats_state(display_home, display_game, "home")
    away_evidence = v5._team_evidence_state(display_away, display_game, "away")
    home_evidence = v5._team_evidence_state(display_home, display_game, "home")

    st.markdown(prior._monster_matchup_hero(identity, away_stats, home_stats), unsafe_allow_html=True)
    st.markdown(prior._compact_game_strip(identity), unsafe_allow_html=True)
    st.markdown(prior._scoring_defense_summary(away_stats, home_stats), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
<div class="gt153-connected-head" data-testid="gt153-connected-evidence-shell">
  <div class="gt153-connected-kicker">CONNECTED GAME TOTAL FLOW • STEP 3</div>
  <div class="gt153-connected-title">Steps 1–10 → Team Evidence → Model Status → Distribution → Final → Top-5</div>
  <div class="gt153-connected-sub">Compact team evidence now stays in the same story. Full team detail remains preserved in one collapsed raw-evidence drawer.</div>
</div>
""",
            unsafe_allow_html=True,
        )
        prior._render_steps_1_10_rail(identity, away_evidence, home_evidence, display_game)
        _render_compact_team_cards(away_evidence, home_evidence)

        with st.expander("🔬 Raw Steps 1–10 evidence", expanded=False):
            _render_raw_team_evidence(away_evidence, home_evidence)

        st.markdown(v5.prior.prior.prior.prior._status_cards(raw, final), unsafe_allow_html=True)

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

        with st.expander("🏆 Top-5 slate scanner", expanded=False):
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
                st.warning("No game cleared the frozen Step-12 qualification thresholds. V152 will not force a Top-5.")
            else:
                st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V155 compact team evidence • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V155 Game Total V7 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "V155_ACTIVE_MARKER",
    "render_cfb_hub",
    "render_game_total_hub",
]
