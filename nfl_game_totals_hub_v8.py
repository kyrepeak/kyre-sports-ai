"""NFL Game Totals V8 — Page Step 8 sportsbook-free total projection.

Additive presentation layer over frozen Game Totals V7. V7 preserves the
verified slate, live FanDuel market, offense-vs-defense, pace/possession,
explosive scoring, red-zone/drive sustainability, and exact game environment.
V8 adds a deterministic model total built only from those certified non-market
contexts. FanDuel stays visible as market context but has 0.0% projection weight.
Market comparison and the final Over/Under read remain OFF until Step 9.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v7 as v7
from sports_api.nfl_game_totals_total_projection_v1 import build_total_projection

MODEL_VERSION = "NFL GAME TOTALS V8 • PAGE STEP 8 TOTAL PROJECTION"
PAGE_BUILD_STEP = 8
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
TOTAL_PROJECTION_ENABLED = True
MARKET_COMPARISON_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True
GAME_ENVIRONMENT_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP8_CSS = r'''
<style>
.kgt-fill.step8{width:80%}
.kgt-proj{margin-top:9px;border:1px solid #675a9b;border-radius:12px;background:linear-gradient(180deg,#151226,#0d0b16);padding:10px}
.kgt-proj-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}.kgt-proj-head b{font-size:.60rem;color:#c8b8ff}.kgt-proj-head span{font-size:.44rem;color:#8d83af;font-weight:900}
.kgt-proj-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.kgt-proj-stat{border:1px solid #383052;border-radius:9px;padding:7px;background:#0d0b16}.kgt-proj-stat span{display:block;font-size:.38rem;color:#8e86a9;font-weight:900;letter-spacing:.04em}.kgt-proj-stat b{display:block;font-size:.80rem;color:#f7f3ff;margin-top:2px}.kgt-proj-stat.total b{font-size:1.05rem;color:#c8b8ff}
.kgt-proj-adjust{margin-top:7px;display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.kgt-proj-chip{border:1px solid #312a48;border-radius:8px;background:#0a0911;padding:6px}.kgt-proj-chip span{display:block;font-size:.36rem;color:#7e7697;font-weight:900}.kgt-proj-chip b{display:block;font-size:.58rem;color:#ded7f5;margin-top:2px}.kgt-proj-note{margin-top:7px;border:1px solid #4a406d;border-radius:9px;padding:7px 8px;background:#121020;font-size:.43rem;color:#9f97bd;line-height:1.4}.kgt-proj-note strong{color:#d9cdff}.kgt-proj-unavailable{border-style:dashed}.kgt-proj-unavailable b{color:#ef9ca8}
@media(max-width:760px){.kgt-proj-grid{grid-template-columns:1fr 1fr}.kgt-proj-adjust{grid-template-columns:1fr 1fr}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v7._safe(value, default)


def _fmt(value: Any, digits: int = 1) -> str:
    try:
        number = float(value)
        return f"{number:.{digits}f}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _fmt_adjustment(value: Any) -> str:
    try:
        number = float(value)
        if not math.isfinite(number):
            return "—"
        return f"{number:+.1f}"
    except (TypeError, ValueError):
        return "—"


def _projection_html(projection: dict[str, Any] | None) -> str:
    payload = projection or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "Certified Step 3-7 projection inputs unavailable.")
        return (
            '<div class="kgt-proj kgt-proj-unavailable">'
            '<div class="kgt-proj-head"><b>🧮 TOTAL PROJECTION • STEP 8</b><span>MODEL ONLY • NO MARKET INPUT</span></div>'
            f'<b>PROJECTION UNAVAILABLE</b><div class="kgt-proj-note">{escape(detail)} • Model fails closed; no fake total is created.</div>'
            '</div>'
        )

    adjustments = payload.get("adjustments") if isinstance(payload.get("adjustments"), dict) else {}
    return (
        '<div class="kgt-proj">'
        '<div class="kgt-proj-head"><b>🧮 TOTAL PROJECTION • STEP 8</b><span>SPORTSBOOK WEIGHT 0.0%</span></div>'
        '<div class="kgt-proj-grid">'
        f'<div class="kgt-proj-stat total"><span>MODEL TOTAL</span><b>{escape(_fmt(payload.get("projected_total")))}</b></div>'
        f'<div class="kgt-proj-stat"><span>SCORING BASELINE</span><b>{escape(_fmt(payload.get("baseline_total")))}</b></div>'
        f'<div class="kgt-proj-stat"><span>MODEL RANGE</span><b>{escape(_fmt(payload.get("range_low")))}–{escape(_fmt(payload.get("range_high")))}</b></div>'
        '</div>'
        '<div class="kgt-proj-adjust">'
        f'<div class="kgt-proj-chip"><span>PACE</span><b>{escape(_fmt_adjustment(adjustments.get("pace")))}</b></div>'
        f'<div class="kgt-proj-chip"><span>EXPLOSIVES</span><b>{escape(_fmt_adjustment(adjustments.get("explosive")))}</b></div>'
        f'<div class="kgt-proj-chip"><span>SUSTAINABILITY</span><b>{escape(_fmt_adjustment(adjustments.get("sustainability")))}</b></div>'
        f'<div class="kgt-proj-chip"><span>ENVIRONMENT</span><b>{escape(_fmt_adjustment(adjustments.get("environment")))}</b></div>'
        '</div>'
        '<div class="kgt-proj-note"><strong>Projection firewall:</strong> this total is built only from certified Steps 3–7 data. FanDuel line and prices are not accepted by the projection function. Market comparison and the final Over/Under read stay reserved for Step 9.</div>'
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
) -> str:
    base_html = v7._game_card(
        row,
        snapshot,
        scoring_context,
        pace_context,
        explosive_context,
        red_zone_drive_context,
        environment_context,
    )
    section = _projection_html(projection)
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
        ("9", "MARKET + FINAL READ", False),
        ("10", "FINAL CERTIFICATION", False),
    )
    stage_html = "".join(
        f'<div class="kgt-stage{" on" if active else ""}">{number} • {label}</div>'
        for number, label, active in stages
    )
    return (
        '<div class="kgt-progress">'
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 8 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step8"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        v7.v6.v5.v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v7.v6.v5.v4.v3.v2._STEP2_CSS
        + v7.v6.v5.v4.v3._STEP3_CSS
        + v7.v6.v5.v4._STEP4_CSS
        + v7.v6.v5._STEP5_CSS
        + v7.v6._STEP6_CSS
        + v7._STEP7_CSS
        + _STEP8_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 8 turns the sportsbook-free total projection ON. Certified scoring, pace, explosive-play, sustainability, and environment context feed the model; FanDuel stays visible but contributes 0.0% to the projection.</div>'
        + '<div class="kgt-chiprow"><span class="kgt-chip">EXACT ESPN GAME IDs</span><span class="kgt-chip teal">TOTAL PROJECTION ON</span><span class="kgt-chip teal">FANDUEL CONTEXT LIVE</span><span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span></div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN identity stays frozen.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🌦️</div><b>Game Environment</b><span>Step 7 remains connected.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🧮</div><b>Total Projection</b><span>Sportsbook-free model total is live.</span></div>'
        '<div class="kgt-tool"><div class="icon">⚖️</div><b>Market + Final Read</b><span>Reserved for Step 9.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 8 firewall:</strong> projection accepts only certified Steps 3–7 context. '
        '<span class="orange">FanDuel / sportsbook projection influence remains exactly 0.0%.</span> '
        '<span class="teal">No market-vs-model lean or wager action is produced until Step 9.</span></div>',
        unsafe_allow_html=True,
    )


def _projection_contexts(
    games: pd.DataFrame,
    scoring_contexts: dict[str, dict[str, Any]],
    pace_contexts: dict[str, dict[str, Any]],
    explosive_contexts: dict[str, dict[str, Any]],
    red_zone_drive_contexts: dict[str, dict[str, Any]],
    environment_contexts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"), "")
        output[event_id] = build_total_projection(
            scoring_contexts.get(event_id),
            pace_contexts.get(event_id),
            explosive_contexts.get(event_id),
            red_zone_drive_contexts.get(event_id),
            environment_contexts.get(event_id),
        )
    return output


def _render_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> None:
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(games)); c2.metric("Upcoming", upcoming); c3.metric("Live", live); c4.metric("Final", final)

    if not diag.get("request_ok"):
        st.error("NFL schedule provider did not return a usable slate. Game Totals fails closed and no fake games are created.")
        return

    st.caption(f"✅ Verified NFL schedule • {day_str} • connected ESPN context + certified FanDuel market API • sportsbook-free model total • {len(games)} game(s) • kickoff clocks displayed in Phoenix MST")
    st.markdown('<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals + Model Projection</h3><span>STEP 8 • CONNECTED</span></div>', unsafe_allow_html=True)
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("🎰 Loading market context + certified Steps 3–7 + 🧮 sportsbook-free projection…"):
        snapshots = v7.v6.v5.v4.v3.v2._market_snapshots(games)
        scoring_contexts = v7.v6.v5.v4.v3._matchup_contexts(games, day_str)
        pace_contexts = v7.v6.v5.v4._pace_contexts(games, day_str)
        explosive_contexts = v7.v6.v5._explosive_contexts(games, day_str)
        red_zone_drive_contexts = v7.v6._red_zone_drive_contexts(games, day_str)
        environment_contexts = v7._environment_contexts(games, day_str)
        projection_contexts = _projection_contexts(
            games,
            scoring_contexts,
            pace_contexts,
            explosive_contexts,
            red_zone_drive_contexts,
            environment_contexts,
        )

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
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    default_date = st.session_state.get(
        "nfl_game_totals_v8_date",
        st.session_state.get(
            "nfl_game_totals_v7_date",
            st.session_state.get("nfl_game_totals_v6_date", st.session_state.get("nfl_v1_date", pd.Timestamp.now(tz=v7.v6.v5.v4.v3.v2.foundation.ET).date())),
        ),
    )
    selected = st.date_input("📅 NFL Game Totals slate date", value=default_date, key="nfl_game_totals_v8_date_input")
    for key in (
        "nfl_game_totals_v8_date", "nfl_game_totals_v7_date", "nfl_game_totals_v6_date",
        "nfl_game_totals_v5_date", "nfl_game_totals_v4_date", "nfl_game_totals_v3_date",
        "nfl_game_totals_v2_date", "nfl_game_totals_v1_date", "nfl_v1_date",
    ):
        st.session_state[key] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • projection ON • market comparison OFF • live market ON • Steps 3-7 context ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V8 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "EXPLOSIVE_SCORING_ENABLED",
    "GAME_ENVIRONMENT_ENABLED",
    "LIVE_MARKET_ENABLED",
    "MARKET_COMPARISON_ENABLED",
    "MODEL_VERSION",
    "OFFENSE_DEFENSE_ENABLED",
    "PACE_POSSESSION_ENABLED",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PROJECTION_MODEL_ENABLED",
    "RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TOTAL_PROJECTION_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_game_card",
    "_progress_html",
    "_projection_contexts",
    "_projection_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
