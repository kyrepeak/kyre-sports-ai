"""NFL Game Totals V9 — Step 9 market comparison + final read.

Extends the certified V8.1 mobile/runtime surface. The Step 8 projection is
computed first and remains sportsbook-free. V9 compares that finished model
range with the exact active FanDuel total to produce OVER / UNDER / PASS only.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v8 as v8
import nfl_game_totals_hub_v8_1 as mobile
from sports_api.nfl_game_totals_market_read_v1 import build_market_final_read

MODEL_VERSION = "NFL GAME TOTALS V9 • PAGE STEP 9 MARKET + FINAL READ"
PAGE_BUILD_STEP = 9
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
TOTAL_PROJECTION_ENABLED = True
MARKET_COMPARISON_ENABLED = True
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True
GAME_ENVIRONMENT_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP9_CSS = r'''
<style>
.kgt-fill.step9{width:90%}
.kgt-read{margin-top:9px;border:1px solid #365d68;border-radius:12px;background:linear-gradient(180deg,#0e1b20,#0b1115);padding:10px}
.kgt-read-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.kgt-read-head b{font-size:.60rem;color:#9de6f2}.kgt-read-badge{border:1px solid #416c78;border-radius:999px;padding:3px 7px;font-size:.46rem;font-weight:950;color:#b9edf4}.kgt-read-badge.over{color:#ffbd7a;border-color:#8a5f34}.kgt-read-badge.under{color:#83e9c9;border-color:#347965}.kgt-read-badge.pass{color:#c8c2d7;border-color:#5c5570}.kgt-read-badge.unavailable{color:#ef9ca8;border-color:#75414a}
.kgt-read-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}.kgt-read-stat{border:1px solid #29414a;border-radius:9px;padding:7px;background:#0a1013}.kgt-read-stat span{display:block;font-size:.38rem;color:#76929c;font-weight:900}.kgt-read-stat b{display:block;font-size:.78rem;color:#edf8fa;margin-top:2px}.kgt-read-note{margin-top:7px;font-size:.43rem;color:#8da6ae;line-height:1.4}.kgt-read-note strong{color:#c9edf2}
@media(max-width:760px){.kgt-read-grid{grid-template-columns:1fr 1fr}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v8._safe(value, default)


def _fmt(value: Any, digits: int = 1) -> str:
    try:
        number = float(value)
        return f"{number:.{digits}f}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _american(value: Any) -> str:
    try:
        number = float(value)
        if not math.isfinite(number):
            return "—"
        rounded = int(round(number))
        return f"+{rounded}" if rounded > 0 else str(rounded)
    except (TypeError, ValueError):
        return "—"


def _market_read_html(read: dict[str, Any] | None) -> str:
    payload = read or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "Market comparison unavailable.")
        return (
            '<div class="kgt-read">'
            '<div class="kgt-read-head"><b>⚖️ MARKET + FINAL READ • STEP 9</b><span class="kgt-read-badge unavailable">UNAVAILABLE</span></div>'
            f'<div class="kgt-read-note">{escape(detail)} The comparison fails closed; no wager action is created.</div>'
            '</div>'
        )
    final_read = str(payload.get("final_read") or "PASS").upper()
    badge = final_read.lower() if final_read in {"OVER", "UNDER", "PASS"} else "unavailable"
    return (
        '<div class="kgt-read">'
        f'<div class="kgt-read-head"><b>⚖️ MARKET + FINAL READ • STEP 9</b><span class="kgt-read-badge {badge}">{escape(final_read)}</span></div>'
        '<div class="kgt-read-grid">'
        f'<div class="kgt-read-stat"><span>MODEL TOTAL</span><b>{escape(_fmt(payload.get("model_total")))}</b></div>'
        f'<div class="kgt-read-stat"><span>FANDUEL TOTAL</span><b>{escape(_fmt(payload.get("market_total")))}</b></div>'
        f'<div class="kgt-read-stat"><span>MODEL − MARKET</span><b>{escape(_fmt(payload.get("edge_points")))}</b></div>'
        f'<div class="kgt-read-stat"><span>OVER / UNDER</span><b>{escape(_american(payload.get("over_price")))} / {escape(_american(payload.get("under_price")))}</b></div>'
        '</div>'
        f'<div class="kgt-read-note"><strong>{escape(_safe(payload.get("rationale")))}</strong> Comparison only • sportsbook projection influence 0.0% • stake sizing OFF • wager actions OFF.</div>'
        '</div>'
    )


def _game_card(
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
    base_html = v8._game_card(
        row,
        snapshot,
        scoring_context,
        pace_context,
        explosive_context,
        red_zone_drive_context,
        environment_context,
        projection,
    )
    section = _market_read_html(market_read)
    if base_html.endswith("</div>"):
        return base_html[:-6] + section + "</div>"
    return base_html + section


def _progress_html() -> str:
    stages = (
        ("1", "VERIFIED SLATE", True),
        ("2", "LIVE TOTAL", True),
        ("3", "OFFENSE VS DEFENSE", True),
        ("4", "PACE + POSSESSION", True),
        ("5", "EXPLOSIVE SCORING", True),
        ("6", "RED ZONE + DRIVES", True),
        ("7", "GAME ENVIRONMENT", True),
        ("8", "TOTAL PROJECTION", True),
        ("9", "MARKET + FINAL READ", True),
        ("10", "FINAL CERTIFICATION", False),
    )
    stage_html = "".join(
        f'<div class="kgt-stage{" on" if active else ""}">{number} • {label}</div>'
        for number, label, active in stages
    )
    return (
        '<div class="kgt-progress">'
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 9 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step9"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    css = (
        v8.v7.v6.v5.v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v8.v7.v6.v5.v4.v3.v2._STEP2_CSS
        + v8.v7.v6.v5.v4.v3._STEP3_CSS
        + v8.v7.v6.v5.v4._STEP4_CSS
        + v8.v7.v6.v5._STEP5_CSS
        + v8.v7.v6._STEP6_CSS
        + v8.v7._STEP7_CSS
        + v8._STEP8_CSS
        + _STEP9_CSS
    )
    st.markdown(
        css
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 9 compares the completed sportsbook-free model total with the exact active FanDuel total and returns OVER, UNDER, or PASS. The market never feeds back into projection math.</div>'
        + '<div class="kgt-chiprow"><span class="kgt-chip teal">MODEL RANGE LOCKED</span><span class="kgt-chip teal">MARKET COMPARISON ON</span><span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span><span class="kgt-chip lock">WAGER ACTIONS OFF</span></div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 9 firewall:</strong> the model total/range is finalized before the live market is read. '
        '<span class="orange">FanDuel is comparison-only and contributes exactly 0.0% to projection math.</span> '
        '<span class="teal">A line inside the model range is PASS; no stake sizing or wager execution is enabled.</span></div>',
        unsafe_allow_html=True,
    )


def _market_read_contexts(
    projections: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    keys = set(projections) | set(snapshots)
    return {key: build_market_final_read(projections.get(key), snapshots.get(key)) for key in keys}


def _render_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> None:
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(games)); c2.metric("Upcoming", upcoming); c3.metric("Live", live); c4.metric("Final", final)
    if not diag.get("request_ok"):
        st.error("NFL schedule provider did not return a usable slate. Game Totals fails closed and no fake games are created.")
        return
    st.caption(f"✅ Verified NFL schedule • {day_str} • certified context + sportsbook-free projection + comparison-only FanDuel read • {len(games)} game(s) • kickoff clocks displayed in Phoenix MST")
    st.markdown('<div class="kgt-section"><h3>🏟️ Verified Matchups + Model vs Market Final Read</h3><span>STEP 9 • CONNECTED</span></div>', unsafe_allow_html=True)
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("⚖️ Loading certified context, sportsbook-free projection, and comparison-only final read…"):
        snapshots = v8.v7.v6.v5.v4.v3.v2._market_snapshots(games)
        scoring_contexts = v8.v7.v6.v5.v4.v3._matchup_contexts(games, day_str)
        pace_contexts = v8.v7.v6.v5.v4._pace_contexts(games, day_str)
        explosive_contexts = v8.v7.v6.v5._explosive_contexts(games, day_str)
        red_zone_drive_contexts = v8.v7.v6._red_zone_drive_contexts(games, day_str)
        environment_contexts = v8.v7._environment_contexts(games, day_str)
        projection_contexts = v8._projection_contexts(
            games,
            scoring_contexts,
            pace_contexts,
            explosive_contexts,
            red_zone_drive_contexts,
            environment_contexts,
        )
        market_reads = _market_read_contexts(projection_contexts, snapshots)

    cards = "".join(
        _game_card(
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
    _render_hero()
    today = pd.Timestamp.now(tz=v8.v7.v6.v5.v4.v3.v2.foundation.ET).date()
    mobile._apply_pending_date(today)
    selected = mobile._initial_date(today)
    selected = mobile._auto_surface_next_slate(selected, today)
    selected = st.date_input("📅 NFL Game Totals slate date", value=selected, key=mobile._WIDGET_DATE_KEY)
    selected = mobile._as_date(selected, today)
    mobile._sync_game_totals_date(selected)
    feedback = st.session_state.pop(mobile._FEEDBACK_KEY, None)
    if feedback:
        st.info(str(feedback))
    mobile._render_mobile_controls(selected)
    day_str = selected.isoformat()
    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    if isinstance(diag, dict) and diag.get("request_ok") is True and games.empty:
        st.info("No verified NFL games were returned for this date. Tap **Next Game Day** above or **Reload Data** to refresh without rebooting Streamlit.")
    st.caption(f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • market comparison ON • stake sizing OFF • wager actions OFF")


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V9 only renders the Game Total market.")
    return render_nfl_game_totals_hub()
