"""CFB Game Total Clean Page V5 — two-team Evidence Center.

Additive over closed V4 team-stat work. Frozen Game Total analysis still runs
first on the untouched selected game. V5 adds accessible display-only evidence
for each team before any model gate/deep-audit section.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v4 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V5 • V152 EVIDENCE CENTER"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v4"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display

_V152_EVIDENCE_CSS = r"""
<style>
.gt152-evidence{margin:10px 0}.gt152-evtitle{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt152-evtitle b{color:#edf5fb;font-size:.58rem;font-weight:950;letter-spacing:.07em}.gt152-evtitle span{color:#7e91a2;font-size:.34rem}.gt152-evsummary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-bottom:7px}.gt152-evcard{padding:9px;border-radius:14px;background:linear-gradient(145deg,#091722,#0c1620);border:1px solid rgba(121,98,191,.24)}.gt152-evhead{display:flex;align-items:center;justify-content:space-between;gap:7px}.gt152-evteam{color:#f5f9fc;font-size:.72rem;font-weight:950}.gt152-evrecord{color:#d8c5ff;font-size:.42rem;font-weight:950}.gt152-evmetrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.gt152-evmetric{padding:6px;border-radius:8px;background:#0b1924;border:1px solid rgba(122,142,161,.12)}.gt152-evmetric b{display:block;color:#edf4f9;font-size:.54rem}.gt152-evmetric span{display:block;color:#71869a;font-size:.24rem;font-weight:850;margin-top:2px;text-transform:uppercase}.gt152-evsource{margin-top:6px;color:#74899a;font-size:.29rem;line-height:1.4;overflow-wrap:anywhere}.gt152-evsource strong{color:#9adab9}@media(max-width:760px){.gt152-evsummary{grid-template-columns:1fr}.gt152-evmetrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _team_evidence_state(
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    """Return display-only evidence derived from the closed V4 stats state."""
    stats = prior._team_stats_state(profile, game, side)
    completed_games = [
        dict(row)
        for row in (profile.get("completed_games") or [])
        if isinstance(row, Mapping)
    ]
    official_stats = {
        str(key): dict(value)
        for key, value in (profile.get("official_stats") or {}).items()
        if isinstance(value, Mapping)
    }
    polls = {
        str(key): dict(value)
        for key, value in (profile.get("polls") or {}).items()
        if isinstance(value, Mapping)
    }
    return {
        **stats,
        "team": _clean(stats.get("team")) or _clean(profile.get("team")) or side.title(),
        "data_source": _clean(profile.get("data_source")) or _clean(stats.get("source")) or "Completed-game evidence",
        "completed_games": completed_games,
        "official_stats": official_stats,
        "polls": polls,
        "rank_source": _clean(profile.get("rank_source")),
        "head_coach": _clean(profile.get("head_coach")),
        "division_context": _clean(profile.get("division_context")),
        "conference": _clean(profile.get("conference")),
        "runtime_reconciled": bool(profile.get("runtime_reconciled") or profile.get("deep_data_reconciled")),
    }


def _fmt_num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


def _evidence_summary_card(state: Mapping[str, Any]) -> str:
    return f"""
<div class="gt152-evcard">
  <div class="gt152-evhead"><div class="gt152-evteam">{escape(_clean(state.get('team')))}</div><div class="gt152-evrecord">{escape(_clean(state.get('record')) or '—')}</div></div>
  <div class="gt152-evmetrics">
    <div class="gt152-evmetric"><b>{escape(_fmt_num(state.get('ppg')))}</b><span>PPG</span></div>
    <div class="gt152-evmetric"><b>{escape(_fmt_num(state.get('allowed_pg')))}</b><span>ALLOWED / GAME</span></div>
    <div class="gt152-evmetric"><b>{escape(_fmt_num(state.get('point_diff_pg')))}</b><span>POINT DIFF / GAME</span></div>
    <div class="gt152-evmetric"><b>{escape(_clean(state.get('recent_form')) or '—')}</b><span>RECENT FORM</span></div>
  </div>
  <div class="gt152-evsource"><strong>DATA SOURCE</strong> • {escape(_clean(state.get('data_source')))}</div>
</div>
"""


def _evidence_summary_html(away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    return f"""
<div class="gt152-evidence" data-testid="gt152-evidence-center-summary">
  <div class="gt152-evtitle"><b>🔎 EVIDENCE CENTER</b><span>Key evidence visible • deep evidence expandable</span></div>
  <div class="gt152-evsummary">{_evidence_summary_card(away)}{_evidence_summary_card(home)}</div>
</div>
"""


def _render_recent_games(state: Mapping[str, Any]) -> None:
    st.markdown("**Recent completed games**")
    games = list(state.get("completed_games") or [])[-5:]
    if not games:
        st.caption("No verified completed-game evidence available.")
        return
    for row in reversed(games):
        opponent = _clean(row.get("opponent")) or "Opponent unavailable"
        result = _clean(row.get("result")) or "—"
        score = _clean(row.get("score")) or "Score unavailable"
        date = _clean(row.get("date")) or "Date unavailable"
        location = _clean(row.get("location")) or "site unavailable"
        st.markdown(f"- **{result} {score}** vs {opponent} • {date} • {location}")


def _render_team_evidence_body(state: Mapping[str, Any]) -> None:
    st.markdown(
        f"**Offense / defense evidence**  \n"
        f"PPG: **{_fmt_num(state.get('ppg'))}** • "
        f"Allowed / game: **{_fmt_num(state.get('allowed_pg'))}** • "
        f"Point diff / game: **{_fmt_num(state.get('point_diff_pg'))}** • "
        f"Recent form: **{_clean(state.get('recent_form')) or '—'}**"
    )
    _render_recent_games(state)
    st.markdown(
        f"**Split context**  \n"
        f"Home: **{_clean(state.get('home_split')) or '—'}** • "
        f"Away: **{_clean(state.get('away_split')) or '—'}** • "
        f"Neutral: **{_clean(state.get('neutral_split')) or '—'}**"
    )
    st.markdown(
        f"**SOS**  \n"
        f"Opponent win rate: **{_fmt_pct(state.get('sos_opponent_win_pct'))}** • "
        f"Coverage: **{_fmt_pct(state.get('sos_coverage'))}**"
    )

    official = state.get("official_stats") or {}
    if official:
        st.markdown("**NCAA stat provenance**")
        shown = 0
        for key, row in official.items():
            if shown >= 5:
                break
            label = _clean(row.get("label")) or _clean(key)
            value = _clean(row.get("value") or row.get("display_value") or row.get("stat"))
            rank = _clean(row.get("rank"))
            detail = " • ".join(part for part in (value, f"Rank {rank}" if rank else "") if part)
            st.markdown(f"- {label}: {detail or 'verified source row'}")
            shown += 1
    else:
        st.caption("NCAA stat provenance: no verified category rows available for this display sample.")

    polls = state.get("polls") or {}
    rank_source = _clean(state.get("rank_source"))
    st.markdown("**Ranking / source provenance**")
    if polls:
        for name, row in polls.items():
            rank = row.get("rank")
            status = f"#{rank}" if rank not in (None, "") else _clean(row.get("state")) or "unranked"
            st.markdown(f"- {name.upper()}: {status}")
    elif rank_source:
        st.markdown(f"- {rank_source}")
    else:
        st.markdown("- Ranking provenance unavailable")

    st.markdown(
        f"**DATA SOURCE**  \n{_clean(state.get('data_source')) or 'Source unavailable'}"
    )
    if _clean(state.get("conference")) or _clean(state.get("division_context")):
        st.caption(
            " • ".join(
                part
                for part in (
                    _clean(state.get("conference")),
                    _clean(state.get("division_context")),
                    _clean(state.get("head_coach")),
                )
                if part
            )
        )


def _render_evidence_center(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    st.markdown(_evidence_summary_html(away, home), unsafe_allow_html=True)
    away_team = _clean(away.get("team")) or "Away team"
    home_team = _clean(home.get("team")) or "Home team"
    with st.expander(f"{away_team} evidence", expanded=False):
        _render_team_evidence_body(away)
    with st.expander(f"{home_team} evidence", expanded=False):
        _render_team_evidence_body(home)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(
        prior.prior.prior.prior._CSS
        + prior.prior.prior._V151_CSS
        + prior.prior._V152_IDENTITY_CSS
        + prior._V152_STATS_CSS
        + _V152_EVIDENCE_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="gt151-head">
  <div class="gt151-kicker">CFB GAME TOTAL • V152 PRODUCTION ACTIVE • EVIDENCE CENTER</div>
  <div class="gt151-title">🏁 College Football Game Total • Monster Dashboard</div>
  <div class="gt151-sub">Exact identity, completed-game team stats, and accessible team evidence. Frozen Step-11/12 Game Total math remains untouched.</div>
  <div class="gt151-chips"><span class="gt151-chip live">V152 PRODUCTION ACTIVE ✅</span><span class="gt151-chip purple">FROZEN MODEL ✅</span><span class="gt151-chip live">EXACT-ID LOGOS</span><span class="gt151-chip live">EVIDENCE CENTER</span><span class="gt151-chip amber">SPORTSBOOK 0.0%</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(prior.prior.prior.prior._PHOENIX).date(),
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

    # FROZEN MODEL PATH: always run the untouched selected game first.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY-ONLY PATH: copied game + Game-Total-only evidence overlay.
    display_game, display_away, display_home, display_diag = runtime_display.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = prior.prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = prior._team_stats_state(display_away, display_game, "away")
    home_stats = prior._team_stats_state(display_home, display_game, "home")
    away_evidence = _team_evidence_state(display_away, display_game, "away")
    home_evidence = _team_evidence_state(display_home, display_game, "home")

    st.markdown(prior.prior._identity_panel(identity), unsafe_allow_html=True)
    st.markdown(prior.prior.prior.prior._quick_read(raw, final), unsafe_allow_html=True)
    st.markdown(prior._stats_panel(away_stats, home_stats), unsafe_allow_html=True)
    _render_evidence_center(away_evidence, home_evidence)
    st.markdown(prior.prior.prior.prior._status_cards(raw, final), unsafe_allow_html=True)

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

    st.caption("🛡️ V152 evidence-center display only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V152 Game Total V5 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_evidence_summary_html",
    "_render_evidence_center",
    "_team_evidence_state",
    "render_cfb_hub",
    "render_game_total_hub",
]
