"""CFB Game Total Clean Page V6 — compact Monster dashboard.

Presentation-only layer over closed V5 Evidence Center. Frozen Game Total
analysis still runs first on the untouched selected game. V6 reorganizes the
same verified display evidence into a compact matchup-first dashboard.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v5 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V6 • V152 COMPACT MONSTER DASHBOARD"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v5"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display

_V152_MONSTER_CSS = r"""
<style>
:root{
  --gt-green:#6fd8a7;
  --gt-red:#ff7f86;
  --gt-amber:#f0c96d;
  --gt-blue:#77b9e8;
  --gt-purple:#bd98ff;
  --gt-gray:#8396a8;
}
.gt152-shell{margin:0 0 10px;padding:11px 12px;border-radius:17px;background:linear-gradient(145deg,#07131e,#0c1723);border:1px solid rgba(111,135,158,.18)}
.gt152-shelltop{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.gt152-kicker{color:var(--gt-purple);font-size:.38rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase}.gt152-title{color:#f7fbff;font-size:1rem;font-weight:950;line-height:1.12;margin-top:2px}.gt152-sub{color:var(--gt-gray);font-size:.36rem;margin-top:4px}.gt152-live{padding:4px 7px;border-radius:999px;color:var(--gt-green);background:rgba(38,111,77,.18);font-size:.32rem;font-weight:950;white-space:nowrap}
.gt152-hero{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:stretch;margin:8px 0 7px}.gt152-hero-team{display:flex;align-items:center;gap:9px;padding:10px;border-radius:14px;background:#0a1925;border:1px solid rgba(116,145,170,.16);min-width:0}.gt152-hero-team.home{flex-direction:row-reverse;text-align:right}.gt152-logo{width:64px;height:64px;object-fit:contain;flex:0 0 64px}.gt152-logo-fallback{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#12293a;color:var(--gt-blue);font-size:1rem;font-weight:950;flex:0 0 64px}.gt152-herotext{min-width:0}.gt152-teamname{color:#f6f9fc;font-size:.86rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt152-record{display:inline-block;margin-top:3px;padding:3px 7px;border-radius:999px;background:rgba(112,73,176,.20);color:var(--gt-purple);font-size:.39rem;font-weight:950}.gt152-teammeta{color:var(--gt-gray);font-size:.30rem;margin-top:4px;line-height:1.35}.gt152-herometrics{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}.gt152-mini{padding:3px 5px;border-radius:6px;background:#0e202e;color:#aebdcc;font-size:.27rem}.gt152-at{display:flex;align-items:center;justify-content:center;color:var(--gt-gray);font-size:.65rem;font-weight:950}
.gt152-game-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin:0 0 7px}.gt152-gamefact{padding:7px 8px;border-radius:9px;background:#0a1823;border:1px solid rgba(119,142,163,.12);min-width:0}.gt152-gamefact b{display:block;color:#e7f1f8;font-size:.45rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt152-gamefact span{display:block;color:var(--gt-blue);font-size:.23rem;font-weight:900;text-transform:uppercase;margin-top:2px}
.gt152-svd{margin:0 0 8px;padding:9px;border-radius:13px;background:linear-gradient(145deg,#0a1622,#0b1a27);border:1px solid rgba(108,139,166,.16)}.gt152-section-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}.gt152-section-title b{color:#eef5fb;font-size:.53rem;font-weight:950;letter-spacing:.07em}.gt152-section-title span{color:var(--gt-gray);font-size:.29rem}.gt152-svdgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt152-svdcard{padding:8px;border-radius:10px;background:#0c1b27}.gt152-svdteam{color:#f5f9fc;font-size:.56rem;font-weight:950}.gt152-svdline{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin-top:6px}.gt152-svdmetric{padding:5px;border-radius:7px;background:#102330}.gt152-svdmetric b{display:block;color:#edf4f9;font-size:.47rem}.gt152-svdmetric span{display:block;color:var(--gt-gray);font-size:.22rem;margin-top:2px;text-transform:uppercase}.gt152-favorable{color:var(--gt-green)!important}.gt152-concern{color:var(--gt-red)!important}.gt152-caution{color:var(--gt-amber)!important}.gt152-info{color:var(--gt-blue)!important}.gt152-model{color:var(--gt-purple)!important}
@media(max-width:760px){.gt152-shelltop{display:block}.gt152-live{display:inline-block;margin-top:6px}.gt152-hero{grid-template-columns:1fr}.gt152-at{padding:0}.gt152-hero-team.home{flex-direction:row;text-align:left}.gt152-game-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.gt152-svdgrid{grid-template-columns:1fr}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _logo(team: Mapping[str, Any], side: str) -> str:
    url = _clean(team.get("logo"))
    name = _clean(team.get("team")) or side.title()
    if url:
        return f'<img class="gt152-logo" data-testid="gt152-{side}-logo" src="{escape(url)}" alt="{escape(name)} logo">'
    initials = "".join(part[:1] for part in name.split() if part)[:2].upper() or "CF"
    return f'<div class="gt152-logo-fallback" data-testid="gt152-{side}-logo-missing">{escape(initials)}</div>'


def _hero_team(identity: Mapping[str, Any], stats: Mapping[str, Any], side: str) -> str:
    name = _clean(identity.get("team")) or _clean(stats.get("team")) or side.title()
    rank = _clean(identity.get("rank")) or "UNRANKED"
    conference = _clean(identity.get("conference")) or "Conference unavailable"
    exact = bool(identity.get("exact_identity"))
    return f"""
<div class="gt152-hero-team {'home' if side == 'home' else ''}" data-testid="gt152-{side}-hero">
  {_logo(identity, side)}
  <div class="gt152-herotext">
    <div class="gt152-teamname">{escape(name)}</div>
    <div class="gt152-record" data-testid="gt152-{side}-record">{escape(_clean(stats.get('record')) or '—')}</div>
    <div class="gt152-teammeta">{escape(rank)} • {escape(conference)} • {'EXACT ID' if exact else 'IDENTITY CHECK'}</div>
    <div class="gt152-herometrics"><span class="gt152-mini">PPG {_num(stats.get('ppg'))}</span><span class="gt152-mini">Allow {_num(stats.get('allowed_pg'))}</span><span class="gt152-mini">Form {escape(_clean(stats.get('recent_form')) or '—')}</span></div>
  </div>
</div>
"""


def _monster_matchup_hero(identity: Mapping[str, Any], away_stats: Mapping[str, Any], home_stats: Mapping[str, Any]) -> str:
    return f"""
<div data-testid="gt152-monster-matchup-hero">
  <div class="gt152-section-title"><b>👹 MONSTER MATCHUP</b><span>Exact identity • current completed-game sample</span></div>
  <div class="gt152-hero">{_hero_team(identity.get('away') or {}, away_stats, 'away')}<div class="gt152-at">@</div>{_hero_team(identity.get('home') or {}, home_stats, 'home')}</div>
</div>
"""


def _compact_game_strip(identity: Mapping[str, Any]) -> str:
    facts = (
        ("Kickoff", _clean(identity.get("kickoff")) or "Unavailable"),
        ("Venue", _clean(identity.get("venue")) or "Unavailable"),
        ("Broadcast", _clean(identity.get("broadcast")) or "Unavailable"),
        ("Status", _clean(identity.get("game_status")) or "Unavailable"),
    )
    cells = "".join(f'<div class="gt152-gamefact"><b>{escape(value)}</b><span>{escape(label)}</span></div>' for label, value in facts)
    return f'<div class="gt152-game-strip" data-testid="gt152-compact-game-strip">{cells}</div>'


def _scoring_defense_summary(away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    def card(team: Mapping[str, Any], opponent: Mapping[str, Any]) -> str:
        ppg = team.get("ppg")
        opponent_allowed = opponent.get("allowed_pg")
        diff = team.get("point_diff_pg")
        return f"""
<div class="gt152-svdcard">
  <div class="gt152-svdteam">{escape(_clean(team.get('team')))}</div>
  <div class="gt152-svdline">
    <div class="gt152-svdmetric"><b class="gt152-info">{_num(ppg)}</b><span>Team PPG</span></div>
    <div class="gt152-svdmetric"><b class="gt152-caution">{_num(opponent_allowed)}</b><span>Opp allowed</span></div>
    <div class="gt152-svdmetric"><b class="{'gt152-favorable' if isinstance(diff, (int, float)) and float(diff) >= 0 else 'gt152-concern'}">{_num(diff)}</b><span>Point diff</span></div>
  </div>
</div>
"""
    return f"""
<div class="gt152-svd" data-testid="gt152-scoring-defense">
  <div class="gt152-section-title"><b>⚔️ SCORING VS DEFENSE</b><span>Simple matchup read • not projection math</span></div>
  <div class="gt152-svdgrid">{card(away, home)}{card(home, away)}</div>
</div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(
        prior.prior.prior.prior.prior._CSS
        + prior.prior.prior.prior._V151_CSS
        + prior._V152_EVIDENCE_CSS
        + _V152_MONSTER_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="gt152-shell">
  <div class="gt152-shelltop">
    <div><div class="gt152-kicker">CFB GAME TOTAL • MONSTER DASHBOARD</div><div class="gt152-title">College Football Game Total</div><div class="gt152-sub">Matchup first. Evidence next. Deep model machinery stays out of the way until you want it.</div></div>
    <div class="gt152-live">V152 PRODUCTION ACTIVE ✅</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(prior.prior.prior.prior.prior._PHOENIX).date(),
        key="cfb_v152_game_total_date",
    )
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)
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

    # FROZEN MODEL PATH: untouched game first.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY-ONLY PATH: copied game; never feeds frozen calculations.
    display_game, display_away, display_home, display_diag = runtime_display.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = prior.prior.prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = prior.prior._team_stats_state(display_away, display_game, "away")
    home_stats = prior.prior._team_stats_state(display_home, display_game, "home")
    away_evidence = prior._team_evidence_state(display_away, display_game, "away")
    home_evidence = prior._team_evidence_state(display_home, display_game, "home")

    st.markdown(_monster_matchup_hero(identity, away_stats, home_stats), unsafe_allow_html=True)
    st.markdown(_compact_game_strip(identity), unsafe_allow_html=True)
    st.markdown(_scoring_defense_summary(away_stats, home_stats), unsafe_allow_html=True)
    prior._render_evidence_center(away_evidence, home_evidence)
    st.markdown(prior.prior.prior.prior.prior._status_cards(raw, final), unsafe_allow_html=True)

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
        if st.button("Run final Game Total Top-5 scan", type="primary", key=f"cfb_v152_scan_button_{selected_day}"):
            with st.spinner("Scanning the verified CFB slate through frozen Steps 11–12..."):
                rows, diag = frozen_page.slate.scan_slate(games, selected_day)
                st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5)
                st.session_state[diag_key] = diag
        top5 = st.session_state.get(scan_key) or []
        diag = st.session_state.get(diag_key) or {}
        if diag:
            st.caption(f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • {int(diag.get('final_ready') or 0)} final-ready • {int(diag.get('qualified_forecasts') or 0)} ranked-eligible • {len(diag.get('errors') or [])} errors")
        if top5:
            for row in top5:
                st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
        elif diag:
            st.warning("No game cleared the frozen Step-12 qualification thresholds. V152 will not force a Top-5.")
        else:
            st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V152 compact display only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V152 Game Total V6 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_compact_game_strip",
    "_monster_matchup_hero",
    "_scoring_defense_summary",
    "render_cfb_hub",
    "render_game_total_hub",
]
