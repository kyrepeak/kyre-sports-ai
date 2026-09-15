"""NFL Game Totals V4 — Page Step 4 pace + possession context.

Additive presentation layer over frozen Game Totals V3. V3 keeps the verified
slate, live FanDuel market, and offense-vs-defense context. V4 adds descriptive
ESPN plays/game and possession/game context beneath the same matchup card.

Projection remains OFF. Sportsbook influence remains exactly 0.0%.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v3 as v3
from sports_api.nfl_game_totals_pace_context_v1 import (
    build_matchup_pace_context,
    build_team_pace_profile,
)

MODEL_VERSION = "NFL GAME TOTALS V4 • PAGE STEP 4 PACE + POSSESSION"
PAGE_BUILD_STEP = 4
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP4_CSS = r'''
<style>
.kgt-fill.step4{width:40%}
.kgt-pace{margin-top:9px;border:1px solid #37464b;border-radius:12px;background:linear-gradient(180deg,#101619,#0c1012);padding:9px}
.kgt-pace-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.kgt-pace-head b{font-size:.58rem;color:#b8d8e2}.kgt-pace-head span{font-size:.44rem;color:#71858e;font-weight:850}
.kgt-pace-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kgt-pace-side{border:1px solid #253239;border-radius:10px;background:#0b1012;padding:8px}.kgt-pace-team{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:6px}.kgt-pace-team strong{font-size:.61rem;color:#f5f7f8}.kgt-pace-signal{font-size:.43rem;font-weight:950;border-radius:999px;padding:3px 6px;border:1px solid #4c6069;color:#bdd1d9}.kgt-pace-signal.high{border-color:#27775f;color:#7ef0bd;background:#10231d}.kgt-pace-signal.balanced{border-color:#746537;color:#f1cf83;background:#211c10}.kgt-pace-signal.low{border-color:#6a4e66;color:#d9aed4;background:#1b131a}
.kgt-pace-stats{display:grid;grid-template-columns:1fr 1fr;gap:5px}.kgt-pace-stat{border:1px solid #222d32;border-radius:8px;padding:6px;background:#090d0f}.kgt-pace-stat span{display:block;font-size:.40rem;color:#76878e;font-weight:900;letter-spacing:.04em}.kgt-pace-stat b{display:block;font-size:.74rem;color:#f0f4f5;margin-top:2px}.kgt-pace-summary{margin-top:7px;border:1px solid #29444f;border-radius:9px;padding:6px 8px;background:#0c1519;display:flex;justify-content:space-between;align-items:center;gap:8px}.kgt-pace-summary span{font-size:.43rem;color:#7e969f}.kgt-pace-summary b{font-size:.54rem;color:#9fdae9}.kgt-pace-note{margin-top:6px;font-size:.42rem;color:#687980;line-height:1.35}.kgt-pace-unavailable{border-style:dashed;color:#8b7780}.kgt-pace-unavailable b{color:#ef9ca8}
@media(max-width:760px){.kgt-pace-grid{grid-template-columns:1fr}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v3._safe(value, default)


def _fmt(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:.1f}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _signal_class(signal: str) -> str:
    value = _safe(signal, "UNAVAILABLE").lower()
    return value if value in {"high", "balanced", "low"} else ""


def _pace_possession_html(context: dict[str, Any] | None) -> str:
    payload = context or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "ESPN pace/possession context unavailable.")
        return (
            '<div class="kgt-pace kgt-pace-unavailable">'
            '<div class="kgt-pace-head"><b>⏱️ PACE + POSSESSION • STEP 4</b><span>DESCRIPTIVE ONLY</span></div>'
            f'<b>CONTEXT UNAVAILABLE</b><div class="kgt-pace-note">{escape(detail)}</div>'
            '</div>'
        )

    side_html: list[str] = []
    for side in ("away", "home"):
        row = payload.get(side) or {}
        signal = _safe(row.get("pace_signal"), "UNAVAILABLE").upper()
        side_html.append(
            '<div class="kgt-pace-side">'
            '<div class="kgt-pace-team">'
            f'<strong>{escape(_safe(row.get("team"), row.get("abbr") or side.title()))}</strong>'
            f'<span class="kgt-pace-signal {_signal_class(signal)}">{escape(signal)}</span>'
            '</div>'
            '<div class="kgt-pace-stats">'
            '<div class="kgt-pace-stat"><span>PLAYS/G</span>'
            f'<b>{escape(_fmt(row.get("plays_per_game")))}</b></div>'
            '<div class="kgt-pace-stat"><span>POSSESSION/G</span>'
            f'<b>{escape(_safe(row.get("possession_clock")))}</b></div>'
            '</div></div>'
        )

    matchup = payload.get("matchup") or {}
    matchup_signal = _safe(matchup.get("pace_signal"), "UNAVAILABLE").upper()
    return (
        '<div class="kgt-pace">'
        '<div class="kgt-pace-head"><b>⏱️ PACE + POSSESSION • STEP 4</b><span>HIGH • BALANCED • LOW</span></div>'
        f'<div class="kgt-pace-grid">{"".join(side_html)}</div>'
        '<div class="kgt-pace-summary">'
        f'<span>Combined opportunity pace • avg team plays/game {_fmt(matchup.get("average_plays_per_game"))}</span>'
        f'<b>{escape(matchup_signal)}</b>'
        '</div>'
        '<div class="kgt-pace-note">ESPN current-season team statistics • Plays/Game + Possession/Game • descriptive only • no market value enters this layer.</div>'
        '</div>'
    )


def _game_card(
    row: Any,
    snapshot: dict[str, Any] | None,
    scoring_context: dict[str, Any] | None,
    pace_context: dict[str, Any] | None,
) -> str:
    base_html = v3._game_card(row, snapshot, scoring_context)
    section = _pace_possession_html(pace_context)
    if base_html.endswith("</div>"):
        return base_html[:-6] + section + "</div>"
    return base_html + section


def _progress_html() -> str:
    stages = (
        ("1", "VERIFIED SLATE", True),
        ("2", "LIVE TOTAL", True),
        ("3", "OFFENSE VS DEFENSE", True),
        ("4", "PACE + POSSESSION", True),
        ("5", "EXPLOSIVE SCORING", False),
        ("6", "RED ZONE + DRIVES", False),
        ("7", "GAME ENVIRONMENT", False),
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
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 4 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step4"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        v3.v2.foundation._GAME_TOTALS_CSS
        + v3.v2._STEP2_CSS
        + v3._STEP3_CSS
        + _STEP4_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 4 adds opportunity pace and possession context beneath the same matchup card. Plays/Game and Possession/Game are descriptive only; projection remains OFF and sportsbook influence stays 0.0%.</div>'
        + '<div class="kgt-chiprow">'
        + '<span class="kgt-chip">EXACT ESPN GAME IDs</span>'
        + '<span class="kgt-chip teal">FANDUEL TOTAL LIVE</span>'
        + '<span class="kgt-chip teal">OFF/DEF LIVE</span>'
        + '<span class="kgt-chip teal">PACE + POSSESSION LIVE</span>'
        + '<span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span>'
        + '</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN identity remains frozen.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + Over/Under remain live.</span></div>'
        '<div class="kgt-tool live"><div class="icon">⚔️</div><b>Offense vs Defense</b><span>PF/G vs opponent PA/G remains connected.</span></div>'
        '<div class="kgt-tool live"><div class="icon">⏱️</div><b>Pace + Possession</b><span>Plays/Game and Possession/Game show opportunity volume.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 4 firewall:</strong> pace and possession are descriptive only. '
        '<span class="orange">Projection remains OFF and sportsbook influence stays 0.0%.</span> '
        '<span class="teal">The same matchup card continues growing downward.</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=21600, show_spinner=False)
def _cached_pace_profiles(day_str: str, team_rows: tuple[tuple[str, str], ...]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    unique = list(dict.fromkeys((str(abbr).upper(), str(name)) for abbr, name in team_rows if str(abbr).strip()))
    if not unique:
        return profiles
    with ThreadPoolExecutor(max_workers=min(8, len(unique))) as pool:
        futures = {
            pool.submit(build_team_pace_profile, abbr, name, day_str): abbr
            for abbr, name in unique
        }
        for future in as_completed(futures):
            abbr = futures[future]
            try:
                profiles[abbr] = future.result()
            except Exception as exc:
                profiles[abbr] = {
                    "abbr": abbr,
                    "ready": False,
                    "diagnostics": [str(exc)],
                    "descriptive_only": True,
                    "sportsbook_projection_weight": 0.0,
                }
    return profiles


def _pace_contexts(games: pd.DataFrame, day_str: str) -> dict[str, dict[str, Any]]:
    if games.empty:
        return {}
    team_rows: list[tuple[str, str]] = []
    for _, row in games.iterrows():
        team_rows.extend(
            [
                (_safe(row.get("away_abbr"), ""), _safe(row.get("away_team"), "Away")),
                (_safe(row.get("home_abbr"), ""), _safe(row.get("home_team"), "Home")),
            ]
        )
    profiles = _cached_pace_profiles(day_str, tuple(team_rows))
    output: dict[str, dict[str, Any]] = {}
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"), "")
        output[event_id] = build_matchup_pace_context(
            _safe(row.get("away_abbr"), ""),
            _safe(row.get("away_team"), "Away"),
            _safe(row.get("home_abbr"), ""),
            _safe(row.get("home_team"), "Home"),
            day_str,
            profiles=profiles,
        )
    return output


def _render_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> None:
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(games))
    c2.metric("Upcoming", upcoming)
    c3.metric("Live", live)
    c4.metric("Final", final)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. Game Totals fails closed and no fake games are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        return

    st.caption(
        f"✅ Verified NFL schedule • {day_str} • ESPN scoring + pace context + certified FanDuel market API • {len(games)} game(s) • kickoff clocks displayed in Phoenix MST"
    )
    st.markdown(
        '<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals + Connected Context</h3><span>STEP 4 • CONNECTED</span></div>',
        unsafe_allow_html=True,
    )
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("🎰 Loading live totals + ⚔️ scoring + ⏱️ pace/possession…"):
        snapshots = v3.v2._market_snapshots(games)
        scoring_contexts = v3._matchup_contexts(games, day_str)
        pace_contexts = _pace_contexts(games, day_str)
    cards = "".join(
        _game_card(
            row,
            snapshots.get(_safe(row.get("game_id"), "")),
            scoring_contexts.get(_safe(row.get("game_id"), "")),
            pace_contexts.get(_safe(row.get("game_id"), "")),
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    default_date = st.session_state.get(
        "nfl_game_totals_v4_date",
        st.session_state.get(
            "nfl_game_totals_v3_date",
            st.session_state.get(
                "nfl_game_totals_v2_date",
                st.session_state.get("nfl_game_totals_v1_date", st.session_state.get("nfl_v1_date", pd.Timestamp.now(tz=v3.v2.foundation.ET).date())),
            ),
        ),
    )
    selected = st.date_input("📅 NFL Game Totals slate date", value=default_date, key="nfl_game_totals_v4_date_input")
    for key in ("nfl_game_totals_v4_date", "nfl_game_totals_v3_date", "nfl_game_totals_v2_date", "nfl_game_totals_v1_date", "nfl_v1_date"):
        st.session_state[key] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v3.v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • projection OFF • live market ON • offense/defense ON • pace/possession ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V4 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "LIVE_MARKET_ENABLED",
    "MODEL_VERSION",
    "OFFENSE_DEFENSE_ENABLED",
    "PACE_POSSESSION_ENABLED",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PROJECTION_MODEL_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_game_card",
    "_pace_possession_html",
    "_progress_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
