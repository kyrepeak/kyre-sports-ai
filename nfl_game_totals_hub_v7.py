"""NFL Game Totals V7 — Page Step 7 game environment.

Additive presentation layer over frozen Game Totals V6. V6 preserves the
verified slate, live FanDuel market, offense-vs-defense, pace/possession,
explosive-scoring, and red-zone/drive-sustainability layers. V7 adds exact ESPN
event venue + weather context beneath the same matchup card.

Indoor games explicitly neutralize outside weather. Outdoor weather is shown as
LOW / WATCH / HIGH descriptive pressure only. Projection remains OFF and
sportsbook influence stays 0.0%; no sportsbook value enters environment logic.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v6 as v6
from sports_api.nfl_game_totals_environment_context_v1 import build_slate_environment_context

MODEL_VERSION = "NFL GAME TOTALS V7 • PAGE STEP 7 GAME ENVIRONMENT"
PAGE_BUILD_STEP = 7
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True
GAME_ENVIRONMENT_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP7_CSS = r'''
<style>
.kgt-fill.step7{width:70%}
.kgt-env{margin-top:9px;border:1px solid #315d66;border-radius:12px;background:linear-gradient(180deg,#0e181b,#0b1113);padding:9px}
.kgt-env-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.kgt-env-head b{font-size:.58rem;color:#8de9f3}.kgt-env-head span{font-size:.44rem;color:#6f9ca3;font-weight:850}
.kgt-env-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.kgt-env-stat{border:1px solid #243f45;border-radius:8px;padding:6px;background:#091012}.kgt-env-stat span{display:block;font-size:.38rem;color:#6e969d;font-weight:900;letter-spacing:.03em}.kgt-env-stat b{display:block;font-size:.69rem;color:#edf8f9;margin-top:2px}
.kgt-env-summary{margin-top:7px;border:1px solid #315d66;border-radius:9px;padding:6px 8px;background:#0c181b;display:flex;justify-content:space-between;align-items:center;gap:8px}.kgt-env-summary span{font-size:.43rem;color:#80a8ae}.kgt-env-pressure{font-size:.49rem;font-weight:950;border-radius:999px;padding:3px 7px;border:1px solid #52757b;color:#d6e4e6}.kgt-env-pressure.low{border-color:#27775f;color:#7ef0bd;background:#10231d}.kgt-env-pressure.watch{border-color:#8a6e2e;color:#f1cf83;background:#211c10}.kgt-env-pressure.high{border-color:#8b3c4b;color:#ff9daa;background:#281217}.kgt-env-pressure.indoor{border-color:#3b6d8f;color:#9fdcff;background:#10202b}
.kgt-env-note{margin-top:6px;font-size:.42rem;color:#678188;line-height:1.35}.kgt-env-unavailable{border-style:dashed}.kgt-env-unavailable b{color:#ef9ca8}
@media(max-width:760px){.kgt-env-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v6._safe(value, default)


def _fmt_number(value: Any, suffix: str = "") -> str:
    try:
        number = float(value)
        return f"{number:.0f}{suffix}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _pressure_class(value: Any) -> str:
    pressure = _safe(value, "UNAVAILABLE").lower()
    return pressure if pressure in {"low", "watch", "high", "indoor"} else ""


def _environment_html(context: dict[str, Any] | None) -> str:
    payload = context or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "Exact ESPN venue/weather context unavailable.")
        return (
            '<div class="kgt-env kgt-env-unavailable">'
            '<div class="kgt-env-head"><b>🌦️ GAME ENVIRONMENT • STEP 7</b><span>DESCRIPTIVE ONLY</span></div>'
            f'<b>CONTEXT UNAVAILABLE</b><div class="kgt-env-note">{escape(detail)} • Environment fails closed; projection remains OFF.</div>'
            '</div>'
        )

    indoor = payload.get("indoor") is True
    pressure = "INDOOR" if indoor else _safe(payload.get("weather_pressure"), "UNAVAILABLE").upper()
    venue_type = "INDOOR" if indoor else "OUTDOOR"
    venue_name = _safe(payload.get("venue_name"), "Venue unavailable")
    summary = "WEATHER NEUTRALIZED" if indoor else f"OUTDOOR WEATHER PRESSURE • {pressure}"
    note = (
        "Indoor venue: outside weather is explicitly neutralized and cannot enter the environment signal."
        if indoor
        else "LOW / WATCH / HIGH is descriptive weather pressure only; sportsbook influence stays 0.0%."
    )
    return (
        '<div class="kgt-env">'
        '<div class="kgt-env-head"><b>🌦️ GAME ENVIRONMENT • STEP 7</b><span>LOW • WATCH • HIGH</span></div>'
        '<div class="kgt-env-grid">'
        f'<div class="kgt-env-stat"><span>VENUE TYPE</span><b>{escape(venue_type)}</b></div>'
        f'<div class="kgt-env-stat"><span>TEMP</span><b>{escape(_fmt_number(payload.get("temperature"), "°F"))}</b></div>'
        f'<div class="kgt-env-stat"><span>PRECIP</span><b>{escape(_fmt_number(payload.get("precipitation"), "%"))}</b></div>'
        f'<div class="kgt-env-stat"><span>GUST</span><b>{escape(_fmt_number(payload.get("gust"), " mph"))}</b></div>'
        '</div>'
        '<div class="kgt-env-summary">'
        f'<span>{escape(venue_name)} • {escape(summary)}</span>'
        f'<b class="kgt-env-pressure {_pressure_class(pressure)}">{escape(pressure)}</b>'
        '</div>'
        f'<div class="kgt-env-note">{escape(note)} • Exact ESPN event identity • descriptive only.</div>'
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
) -> str:
    base_html = v6._game_card(row, snapshot, scoring_context, pace_context, explosive_context, red_zone_drive_context)
    section = _environment_html(environment_context)
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
        ("8", "TOTAL PROJECTION", False),
        ("9", "MARKET + FINAL READ", False),
        ("10", "FINAL CERTIFICATION", False),
    )
    stage_html = "".join(
        f'<div class="kgt-stage{" on" if active else ""}">{number} • {label}</div>'
        for number, label, active in stages
    )
    return (
        '<div class="kgt-progress">'
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 7 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step7"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        v6.v5.v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v6.v5.v4.v3.v2._STEP2_CSS
        + v6.v5.v4.v3._STEP3_CSS
        + v6.v5.v4._STEP4_CSS
        + v6.v5._STEP5_CSS
        + v6._STEP6_CSS
        + _STEP7_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 7 adds exact ESPN venue and game-weather context beneath red-zone sustainability. Indoor weather is neutralized. Projection remains OFF and sportsbook influence stays 0.0%.</div>'
        + '<div class="kgt-chiprow"><span class="kgt-chip">EXACT ESPN GAME IDs</span><span class="kgt-chip teal">FANDUEL TOTAL LIVE</span><span class="kgt-chip teal">GAME ENVIRONMENT LIVE</span><span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span></div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN identity stays frozen.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + prices stay live.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🔴</div><b>Red Zone + Sustainability</b><span>Step 6 remains connected.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🌦️</div><b>Game Environment</b><span>Venue + weather context is live.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 7 firewall:</strong> venue/weather context is descriptive only. '
        '<span class="orange">Projection remains OFF and sportsbook influence stays 0.0%.</span> '
        '<span class="teal">Indoor games explicitly show WEATHER NEUTRALIZED.</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_environment_contexts(day_str: str, event_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return build_slate_environment_context(day_str, event_ids)


def _environment_contexts(games: pd.DataFrame, day_str: str) -> dict[str, dict[str, Any]]:
    if games.empty:
        return {}
    event_ids = tuple(
        dict.fromkeys(
            _safe(row.get("game_id"), "")
            for _, row in games.iterrows()
            if _safe(row.get("game_id"), "")
        )
    )
    return _cached_environment_contexts(day_str, event_ids)


def _render_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> None:
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(games)); c2.metric("Upcoming", upcoming); c3.metric("Live", live); c4.metric("Final", final)

    if not diag.get("request_ok"):
        st.error("NFL schedule provider did not return a usable slate. Game Totals fails closed and no fake games are created.")
        return

    st.caption(f"✅ Verified NFL schedule • {day_str} • connected ESPN context + certified FanDuel market API • {len(games)} game(s) • kickoff clocks displayed in Phoenix MST")
    st.markdown('<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals + Connected Context</h3><span>STEP 7 • CONNECTED</span></div>', unsafe_allow_html=True)
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("🎰 Loading live totals + ⚔️ scoring + ⏱️ pace + 💥 explosives + 🔴 red zone + 🌦️ environment…"):
        snapshots = v6.v5.v4.v3.v2._market_snapshots(games)
        scoring_contexts = v6.v5.v4.v3._matchup_contexts(games, day_str)
        pace_contexts = v6.v5.v4._pace_contexts(games, day_str)
        explosive_contexts = v6.v5._explosive_contexts(games, day_str)
        red_zone_drive_contexts = v6._red_zone_drive_contexts(games, day_str)
        environment_contexts = _environment_contexts(games, day_str)

    cards = "".join(
        _game_card(
            row,
            snapshots.get(_safe(row.get("game_id"), "")),
            scoring_contexts.get(_safe(row.get("game_id"), "")),
            pace_contexts.get(_safe(row.get("game_id"), "")),
            explosive_contexts.get(_safe(row.get("game_id"), "")),
            red_zone_drive_contexts.get(_safe(row.get("game_id"), "")),
            environment_contexts.get(_safe(row.get("game_id"), "")),
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    default_date = st.session_state.get(
        "nfl_game_totals_v7_date",
        st.session_state.get(
            "nfl_game_totals_v6_date",
            st.session_state.get(
                "nfl_game_totals_v5_date",
                st.session_state.get("nfl_game_totals_v4_date", st.session_state.get("nfl_v1_date", pd.Timestamp.now(tz=v6.v5.v4.v3.v2.foundation.ET).date())),
            ),
        ),
    )
    selected = st.date_input("📅 NFL Game Totals slate date", value=default_date, key="nfl_game_totals_v7_date_input")
    for key in (
        "nfl_game_totals_v7_date", "nfl_game_totals_v6_date", "nfl_game_totals_v5_date",
        "nfl_game_totals_v4_date", "nfl_game_totals_v3_date", "nfl_game_totals_v2_date",
        "nfl_game_totals_v1_date", "nfl_v1_date",
    ):
        st.session_state[key] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v6.v5.v4.v3.v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • projection OFF • live market ON • offense/defense ON • pace/possession ON • explosive scoring ON • red-zone/sustainability ON • game environment ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V7 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "EXPLOSIVE_SCORING_ENABLED",
    "GAME_ENVIRONMENT_ENABLED",
    "LIVE_MARKET_ENABLED",
    "MODEL_VERSION",
    "OFFENSE_DEFENSE_ENABLED",
    "PACE_POSSESSION_ENABLED",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PROJECTION_MODEL_ENABLED",
    "RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_environment_contexts",
    "_environment_html",
    "_game_card",
    "_progress_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
