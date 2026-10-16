"""NFL Game Totals compact layout repair V1.

Additive presentation-only wrapper over the frozen V10 connected page. The
verified slate, FanDuel market, Steps 3-7 contexts, Step 8 sportsbook-free
projection, and Step 9 final read all continue to come from the certified V10
stack. This module only recomposes those already-certified outputs into one
compact matchup article and tighter game-day controls.
"""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v10 as v10

MODEL_VERSION = "NFL GAME TOTALS COMPACT LAYOUT V1 • V10 CERTIFICATION PRESERVED"
PAGE_BUILD_STEP = v10.PAGE_BUILD_STEP
PAGE_BUILD_TOTAL = v10.PAGE_BUILD_TOTAL
FINAL_CERTIFICATION_ENABLED = v10.FINAL_CERTIFICATION_ENABLED
SPORTSBOOK_PROJECTION_INFLUENCE = v10.SPORTSBOOK_PROJECTION_INFLUENCE
PROJECTION_MODEL_ENABLED = v10.PROJECTION_MODEL_ENABLED
TOTAL_PROJECTION_ENABLED = v10.TOTAL_PROJECTION_ENABLED
MARKET_COMPARISON_ENABLED = v10.MARKET_COMPARISON_ENABLED
LIVE_MARKET_ENABLED = v10.LIVE_MARKET_ENABLED
OFFENSE_DEFENSE_ENABLED = v10.OFFENSE_DEFENSE_ENABLED
PACE_POSSESSION_ENABLED = v10.PACE_POSSESSION_ENABLED
EXPLOSIVE_SCORING_ENABLED = v10.EXPLOSIVE_SCORING_ENABLED
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = v10.RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED
GAME_ENVIRONMENT_ENABLED = v10.GAME_ENVIRONMENT_ENABLED
STAKE_SIZING_ENABLED = v10.STAKE_SIZING_ENABLED
WAGER_ACTIONS_ENABLED = v10.WAGER_ACTIONS_ENABLED

v9 = v10.v9
v8 = v9.v8
v7 = v8.v7
v6 = v7.v6
v5 = v6.v5
v4 = v5.v4
v3 = v4.v3
v2 = v3.v2
foundation = v2.foundation
mobile = v9.mobile

_COMPACT_CSS = r'''
<style>
/* V10 remains authoritative; these rules only reduce visual footprint. */
.kgt-page{max-width:1240px!important}
.kgt-hero{padding:13px 16px 12px!important;margin:4px 0 8px!important;border-radius:16px!important;box-shadow:0 8px 24px rgba(0,0,0,.16)!important}
.kgt-kicker{font-size:.55rem!important}.kgt-title{font-size:1.42rem!important;margin-top:3px!important}.kgt-sub{font-size:.67rem!important;line-height:1.35!important;margin-top:5px!important;max-width:980px!important}
.kgt-chiprow{gap:5px!important;margin-top:8px!important}.kgt-chip{padding:4px 7px!important;font-size:.51rem!important}
.kgt-progress{padding:8px 10px!important;margin:0 0 7px!important;border-radius:11px!important}.kgt-track,.kgt-rail-wrap{display:none!important}.kgt-progress-top b{font-size:.60rem!important}.kgt-progress-top span{font-size:.52rem!important}
.kgt-cert{padding:7px 9px!important;margin:0 0 8px!important;border-radius:10px!important}.kgt-cert b{font-size:.56rem!important}.kgt-cert span{font-size:.40rem!important;line-height:1.3!important;margin-top:2px!important}
.kgt-compact-controls{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid #293b49;border-radius:10px;background:#0a141b;padding:6px 9px;margin:4px 0 6px;color:#8fa5b4;font-size:.54rem}.kgt-compact-controls b{color:#eef5f8;font-size:.60rem}
.kgt-slate-strip{display:flex;flex-wrap:wrap;align-items:center;gap:7px;border:1px solid #293b49;border-radius:10px;background:#091218;padding:7px 9px;margin:6px 0}.kgt-slate-strip b{color:#edf4f8;font-size:.61rem}.kgt-slate-strip span{border:1px solid #2f4554;border-radius:999px;padding:3px 6px;color:#8ea3b1;font-size:.48rem;font-weight:850}.kgt-slate-strip .live{color:#7ff2c2;border-color:#27775f}
.kgt-section{margin:10px 0 6px!important}.kgt-section h3{font-size:.83rem!important}.kgt-section span{font-size:.48rem!important}
.kgt-grid{grid-template-columns:1fr!important;gap:9px!important}
.kgt-compact-game{padding:10px!important;border-radius:14px!important;box-shadow:0 5px 16px rgba(0,0,0,.12)!important}
.kgt-compact-matchup{border:1px solid #263d4c;border-radius:11px;background:#0a141b;padding:8px 9px}
.kgt-compact-teams{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:center;margin-top:7px}.kgt-compact-teams .kgt-team{margin:0!important}.kgt-compact-teams .kgt-team:last-child{justify-content:flex-end}.kgt-compact-vs{color:#587080;font-size:.48rem;font-weight:950;text-align:center}.kgt-compact-meta{display:flex!important;flex-wrap:wrap;gap:5px 12px!important;margin-top:7px!important;padding-top:6px!important;font-size:.48rem!important}
.kgt-compact-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:7px}
.kgt-compact-summary>.market,.kgt-compact-summary>.kgt-proj,.kgt-compact-summary>.kgt-read{margin:0!important;padding:7px!important;min-width:0;height:100%;box-sizing:border-box}
.kgt-compact-summary .kgt-market-foot,.kgt-compact-summary .kgt-proj-note,.kgt-compact-summary .kgt-read-note{display:none!important}
.kgt-compact-summary .kgt-market-grid,.kgt-compact-summary .kgt-proj-grid,.kgt-compact-summary .kgt-read-grid{gap:4px!important;margin-top:5px!important}.kgt-compact-summary .kgt-proj-adjust{gap:3px!important;margin-top:4px!important}
.kgt-compact-analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:7px}
.kgt-compact-analysis-grid>.kgt-od,.kgt-compact-analysis-grid>.kgt-pace,.kgt-compact-analysis-grid>.kgt-boom,.kgt-compact-analysis-grid>.kgt-rz,.kgt-compact-analysis-grid>.kgt-env{margin:0!important;padding:8px!important;min-width:0;height:100%;box-sizing:border-box}
.kgt-compact-analysis-grid>.kgt-env{grid-column:1/-1}
.kgt-compact-game .kgt-od-note,.kgt-compact-game .kgt-pace-note,.kgt-compact-game .kgt-boom-note,.kgt-compact-game .kgt-rz-note,.kgt-compact-game .kgt-env-note{font-size:.38rem!important;line-height:1.22!important;margin-top:4px!important}
.kgt-compact-game .kgt-od-head,.kgt-compact-game .kgt-pace-head,.kgt-compact-game .kgt-boom-head,.kgt-compact-game .kgt-rz-head,.kgt-compact-game .kgt-env-head{margin-bottom:5px!important}
@media(max-width:900px){.kgt-compact-summary{grid-template-columns:1fr 1fr}.kgt-compact-summary>.kgt-read{grid-column:1/-1}.kgt-compact-analysis-grid{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.kgt-compact-summary,.kgt-compact-analysis-grid{grid-template-columns:1fr}.kgt-compact-summary>.kgt-read,.kgt-compact-analysis-grid>.kgt-env{grid-column:auto}.kgt-compact-teams{grid-template-columns:1fr}.kgt-compact-vs{text-align:left;padding-left:52px}.kgt-compact-teams .kgt-team:last-child{justify-content:flex-start}.kgt-hero{padding:11px!important}.kgt-title{font-size:1.25rem!important}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return foundation._safe(value, default)


def _compact_matchup_html(row: Any) -> str:
    state = _safe(row.get("state"), "pre").lower()
    status_class = "live" if state == "in" else ""
    away_name = _safe(row.get("away_team"), "Away")
    home_name = _safe(row.get("home_team"), "Home")
    labels = foundation._phoenix_kickoff(row)
    clock = labels["clock"] if labels else _safe(row.get("tip_et"), "TBD")
    status = _safe(row.get("status"), "Scheduled")
    if state == "pre" and labels:
        status = labels["status"]
    event_id = _safe(row.get("game_id"), "UNVERIFIED")
    away_score = foundation._score(row, "away")
    home_score = foundation._score(row, "home")

    return (
        '<div class="kgt-compact-matchup">'
        '<div class="kgt-game-top">'
        f'<span>{escape(_safe(row.get("season_type"), "NFL"))} • <span class="kgt-id">ESPN {escape(event_id)}</span></span>'
        f'<span class="kgt-status {status_class}">{escape(status)}</span>'
        '</div>'
        '<div class="kgt-compact-teams">'
        '<div class="kgt-team">'
        f'{foundation._logo_html(row.get("away_logo"), row.get("away_abbr"), away_name)}'
        f'<div class="kgt-team-copy"><b>{escape(away_name)}</b><span>{escape(_safe(row.get("away_record")))}</span></div>'
        f'<strong class="kgt-score">{escape(away_score)}</strong></div>'
        '<div class="kgt-compact-vs">AT</div>'
        '<div class="kgt-team">'
        f'{foundation._logo_html(row.get("home_logo"), row.get("home_abbr"), home_name)}'
        f'<div class="kgt-team-copy"><b>{escape(home_name)}</b><span>{escape(_safe(row.get("home_record")))}</span></div>'
        f'<strong class="kgt-score">{escape(home_score)}</strong></div>'
        '</div>'
        '<div class="kgt-meta kgt-compact-meta">'
        f'<span>🕒 {escape(clock)}</span>'
        f'<span>🏟️ {escape(_safe(row.get("venue"), "Venue TBD"))}</span>'
        f'<span>📺 {escape(_safe(row.get("broadcast")))}</span>'
        '</div></div>'
    )


def _compact_game_card(
    row: Any,
    snapshot: dict[str, Any] | None,
    scoring_context: dict[str, Any] | None,
    pace_context: dict[str, Any] | None,
    explosive_context: dict[str, Any] | None,
    red_zone_drive_context: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
    projection: dict[str, Any] | None,
    market_read: dict[str, Any] | None,
) -> str:
    summary = (
        v2._market_html(snapshot)
        + v8._projection_html(projection)
        + v9._market_read_html(market_read)
    )
    analysis = (
        v3._offense_defense_html(scoring_context)
        + v4._pace_possession_html(pace_context)
        + v5._explosive_html(explosive_context)
        + v6._red_zone_drive_html(red_zone_drive_context)
        + v7._environment_html(environment_context)
    )
    return (
        '<article class="kgt-game kgt-compact-game"'
        f' data-espn-event-id="{escape(_safe(row.get("game_id"), "UNVERIFIED"), quote=True)}">'
        + _compact_matchup_html(row)
        + f'<div class="kgt-compact-summary">{summary}</div>'
        + f'<div class="kgt-compact-analysis-grid">{analysis}</div>'
        + '</article>'
    )


def _render_compact_hero() -> None:
    v10._render_hero()
    st.markdown(_COMPACT_CSS, unsafe_allow_html=True)


def _render_compact_controls(selected: Any, today: Any) -> Any:
    st.markdown(
        '<div class="kgt-compact-controls"><b>📅 Game Day Controls</b><span>Date + navigation in one row</span></div>',
        unsafe_allow_html=True,
    )
    date_col, next_col, reload_col = st.columns([1.7, 1, 1])
    with date_col:
        selected = st.date_input(
            "NFL Game Totals slate date",
            value=selected,
            key=mobile._WIDGET_DATE_KEY,
            label_visibility="collapsed",
        )
    selected = mobile._as_date(selected, today)
    mobile._sync_game_totals_date(selected)
    with next_col:
        if st.button("➡️ Next Game Day", key="nfl_game_totals_compact_next_day", use_container_width=True):
            mobile._queue_next_game_day(selected)
    with reload_col:
        if st.button("🔄 Reload Data", key="nfl_game_totals_compact_reload", use_container_width=True):
            mobile._reload_game_totals_data()
    return selected


def _render_compact_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> None:
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0

    st.markdown(
        '<div class="kgt-slate-strip">'
        f'<b>🏟️ {len(games)} verified game(s) • {escape(day_str)}</b>'
        f'<span>{upcoming} upcoming</span><span class="live">{live} live</span><span>{final} final</span>'
        '<span>Phoenix MST</span></div>',
        unsafe_allow_html=True,
    )
    if not isinstance(diag, dict) or diag.get("request_ok") is not True:
        st.error("NFL schedule provider did not return a usable slate. Game Totals fails closed and no fake games are created.")
        return
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        '<div class="kgt-section"><h3>🏟️ Matchups • Market • Model • Final Read</h3><span>10 / 10 CONNECTED • COMPACT VIEW</span></div>',
        unsafe_allow_html=True,
    )
    with st.spinner("🏈 Loading certified NFL Game Totals context…"):
        snapshots = v2._market_snapshots(games)
        scoring_contexts = v3._matchup_contexts(games, day_str)
        pace_contexts = v4._pace_contexts(games, day_str)
        explosive_contexts = v5._explosive_contexts(games, day_str)
        red_zone_drive_contexts = v6._red_zone_drive_contexts(games, day_str)
        environment_contexts = v7._environment_contexts(games, day_str)
        projection_contexts = v10.v9.v8._projection_contexts(
            games,
            scoring_contexts,
            pace_contexts,
            explosive_contexts,
            red_zone_drive_contexts,
            environment_contexts,
        )
        market_reads = v10.v9._market_read_contexts(projection_contexts, snapshots)

    cards = "".join(
        _compact_game_card(
            row,
            snapshots.get(_safe(row.get("game_id"), "")),
            scoring_contexts.get(_safe(row.get("game_id"), "")),
            pace_contexts.get(_safe(row.get("game_id"), "")),
            explosive_contexts.get(_safe(row.get("game_id"), "")),
            red_zone_drive_contexts.get(_safe(row.get("game_id"), "")),
            environment_contexts.get(_safe(row.get("game_id"), "")),
            projection_contexts.get(_safe(row.get("game_id"), "")),
            market_reads.get(_safe(row.get("game_id"), "")),
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_compact_hero()
    today = pd.Timestamp.now(tz=foundation.ET).date()
    mobile._apply_pending_date(today)
    selected = mobile._initial_date(today)
    selected = mobile._auto_surface_next_slate(selected, today)
    selected = _render_compact_controls(selected, today)

    feedback = st.session_state.pop(mobile._FEEDBACK_KEY, None)
    if feedback:
        st.info(str(feedback))

    day_str = selected.isoformat()
    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = foundation.load_nfl_slate(day_str)
    _render_compact_schedule(games, day_str, diag)
    if isinstance(diag, dict) and diag.get("request_ok") is True and games.empty:
        st.info("No verified NFL games were returned for this date. Use **Next Game Day** or **Reload Data** above.")
    st.caption(
        f"{MODEL_VERSION} • V10 model/data contracts preserved • sportsbook projection influence "
        f"{SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • stake sizing OFF • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals Compact Layout V1 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
