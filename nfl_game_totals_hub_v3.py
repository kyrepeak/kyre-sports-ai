"""NFL Game Totals V3 — Page Step 3 offense vs defense context.

Additive presentation layer over frozen Game Totals V2. V2 keeps verified slate
identity and the live FanDuel market. V3 adds descriptive ESPN scoring context
inside the same matchup card: team offense PF/G versus opponent defense PA/G.

This layer is descriptive only. Projection remains OFF and sportsbook influence
stays 0.0%.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v2 as v2
from sports_api.nfl_game_totals_scoring_context_v1 import (
    build_matchup_scoring_context,
    build_team_scoring_profile,
)

MODEL_VERSION = "NFL GAME TOTALS V3 • PAGE STEP 3 OFFENSE VS DEFENSE"
PAGE_BUILD_STEP = 3
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP3_CSS = r'''
<style>
.kgt-fill.step3{width:30%}
.kgt-od{margin-top:9px;border:1px solid #32454f;border-radius:12px;background:linear-gradient(180deg,#10171b,#0d1114);padding:9px}
.kgt-od-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.kgt-od-head b{font-size:.58rem;color:#a9def2}.kgt-od-head span{font-size:.44rem;color:#71858e;font-weight:850}
.kgt-od-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kgt-od-side{border:1px solid #25343c;border-radius:10px;background:#0c1215;padding:8px;min-width:0}.kgt-od-team{display:flex;justify-content:space-between;gap:6px;align-items:center;margin-bottom:6px}.kgt-od-team strong{font-size:.61rem;color:#f5f7f8}.kgt-od-signal{font-size:.43rem;font-weight:950;border-radius:999px;padding:3px 6px;border:1px solid #4b6672;color:#b9d4df}.kgt-od-signal.favorable{border-color:#27775f;color:#7ef0bd;background:#10231d}.kgt-od-signal.medium{border-color:#7e6737;color:#f1cf83;background:#211c10}.kgt-od-signal.tough{border-color:#7b3d48;color:#f2a0aa;background:#211216}.kgt-od-stats{display:grid;grid-template-columns:1fr 1fr;gap:5px}.kgt-od-stat{border:1px solid #222d32;border-radius:8px;padding:6px;background:#0a0e10}.kgt-od-stat span{display:block;font-size:.40rem;color:#76878e;font-weight:900;letter-spacing:.04em}.kgt-od-stat b{display:block;font-size:.74rem;color:#f0f4f5;margin-top:2px}.kgt-od-note{margin-top:7px;font-size:.42rem;color:#687980;line-height:1.35}.kgt-od-unavailable{border-style:dashed;color:#8b7780}.kgt-od-unavailable b{color:#ef9ca8}
@media(max-width:760px){.kgt-od-grid{grid-template-columns:1fr}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v2._safe(value, default)


def _fmt(value: Any) -> str:
    try:
        number = float(value)
        if not math.isfinite(number):
            return "—"
        return f"{number:.1f}"
    except (TypeError, ValueError):
        return "—"


def _signal_class(signal: str) -> str:
    value = _safe(signal, "UNAVAILABLE").lower()
    return value if value in {"favorable", "medium", "tough"} else ""


def _offense_defense_html(context: dict[str, Any] | None) -> str:
    payload = context or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "ESPN scoring context unavailable.")
        return (
            '<div class="kgt-od kgt-od-unavailable">'
            '<div class="kgt-od-head"><b>⚔️ OFFENSE VS DEFENSE • STEP 3</b><span>DESCRIPTIVE ONLY</span></div>'
            f'<b>CONTEXT UNAVAILABLE</b><div class="kgt-od-note">{escape(detail)}</div>'
            '</div>'
        )

    cards: list[str] = []
    for side in ("away", "home"):
        row = payload.get(side) or {}
        signal = _safe(row.get("signal"), "UNAVAILABLE").upper()
        signal_class = _signal_class(signal)
        cards.append(
            '<div class="kgt-od-side">'
            '<div class="kgt-od-team">'
            f'<strong>{escape(_safe(row.get("team"), row.get("abbr") or side.title()))}</strong>'
            f'<span class="kgt-od-signal {signal_class}">{escape(signal)}</span>'
            '</div>'
            '<div class="kgt-od-stats">'
            '<div class="kgt-od-stat"><span>OFFENSE PF/G</span>'
            f'<b>{escape(_fmt(row.get("offense_ppg")))}</b></div>'
            '<div class="kgt-od-stat"><span>OPP DEFENSE PA/G</span>'
            f'<b>{escape(_fmt(row.get("opponent_defense_papg")))}</b></div>'
            '</div>'
            f'<div class="kgt-od-note">Data quality: {escape(_safe(row.get("quality"), "—"))}</div>'
            '</div>'
        )

    return (
        '<div class="kgt-od">'
        '<div class="kgt-od-head"><b>⚔️ OFFENSE VS DEFENSE • STEP 3</b><span>FAVORABLE • MEDIUM • TOUGH</span></div>'
        f'<div class="kgt-od-grid">{"".join(cards)}</div>'
        '<div class="kgt-od-note">ESPN completed regular-season scoring context • descriptive only • no FanDuel value enters this signal.</div>'
        '</div>'
    )


def _game_card(row: Any, snapshot: dict[str, Any] | None, context: dict[str, Any] | None) -> str:
    base_html = v2._game_card(row, snapshot)
    section = _offense_defense_html(context)
    if base_html.endswith("</div>"):
        return base_html[:-6] + section + "</div>"
    return base_html + section


def _progress_html() -> str:
    stages = (
        ("1", "VERIFIED SLATE", True),
        ("2", "LIVE TOTAL", True),
        ("3", "OFFENSE VS DEFENSE", True),
        ("4", "PACE + POSSESSION", False),
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
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 3 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step3"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        v2.foundation._GAME_TOTALS_CSS
        + v2._STEP2_CSS
        + _STEP3_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 3 adds readable team scoring pressure beneath the verified live market: offense PF/G against opponent defense PA/G. Projection remains OFF and sportsbook influence stays 0.0%.</div>'
        + '<div class="kgt-chiprow">'
        + '<span class="kgt-chip">EXACT ESPN GAME IDs</span>'
        + '<span class="kgt-chip teal">FANDUEL TOTAL LIVE</span>'
        + '<span class="kgt-chip teal">OFFENSE VS DEFENSE LIVE</span>'
        + '<span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span>'
        + '</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN identity remains frozen underneath.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + Over/Under prices stay live from Step 2.</span></div>'
        '<div class="kgt-tool live"><div class="icon">⚔️</div><b>Offense vs Defense</b><span>PF/G meets opponent PA/G with readable scoring-pressure labels.</span></div>'
        '<div class="kgt-tool"><div class="icon">🧠</div><b>Total Projection</b><span>TOTAL PROJECTION • STEP 8 — projection remains OFF.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 3 firewall:</strong> scoring context is descriptive only. '
        '<span class="orange">No PF/G, PA/G, or FanDuel value enters projection math yet.</span> '
        '<span class="teal">The same matchup card grows downward as each step is certified.</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=21600, show_spinner=False)
def _cached_team_profiles(day_str: str, team_rows: tuple[tuple[str, str], ...]) -> dict[str, dict[str, Any]]:
    """Fetch unique team profiles concurrently to keep the page responsive."""
    profiles: dict[str, dict[str, Any]] = {}
    unique = list(dict.fromkeys((str(abbr).upper(), str(name)) for abbr, name in team_rows if str(abbr).strip()))
    if not unique:
        return profiles
    with ThreadPoolExecutor(max_workers=min(8, len(unique))) as pool:
        futures = {
            pool.submit(build_team_scoring_profile, abbr, name, day_str): abbr
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
                    "error": str(exc),
                    "descriptive_only": True,
                    "sportsbook_projection_weight": 0.0,
                }
    return profiles


def _matchup_contexts(games: pd.DataFrame, day_str: str) -> dict[str, dict[str, Any]]:
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
    profiles = _cached_team_profiles(day_str, tuple(team_rows))
    output: dict[str, dict[str, Any]] = {}
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"), "")
        output[event_id] = build_matchup_scoring_context(
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
        f"✅ Verified NFL schedule • {day_str} • ESPN scoring context + certified FanDuel market API • {len(games)} game(s) • "
        "kickoff clocks displayed in Phoenix MST"
    )
    st.markdown(
        '<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals + Scoring Context</h3><span>STEP 3 • CONNECTED</span></div>',
        unsafe_allow_html=True,
    )
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("🎰 Loading exact FanDuel totals + ⚔️ offense/defense context…"):
        snapshots = v2._market_snapshots(games)
        contexts = _matchup_contexts(games, day_str)
    cards = "".join(
        _game_card(
            row,
            snapshots.get(_safe(row.get("game_id"), "")),
            contexts.get(_safe(row.get("game_id"), "")),
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    default_date = st.session_state.get(
        "nfl_game_totals_v3_date",
        st.session_state.get(
            "nfl_game_totals_v2_date",
            st.session_state.get("nfl_game_totals_v1_date", st.session_state.get("nfl_v1_date", pd.Timestamp.now(tz=v2.foundation.ET).date())),
        ),
    )
    selected = st.date_input(
        "📅 NFL Game Totals slate date",
        value=default_date,
        key="nfl_game_totals_v3_date_input",
    )
    st.session_state["nfl_game_totals_v3_date"] = selected
    st.session_state["nfl_game_totals_v2_date"] = selected
    st.session_state["nfl_game_totals_v1_date"] = selected
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • "
        "projection OFF • live market ON • offense/defense descriptive context ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V3 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "LIVE_MARKET_ENABLED",
    "MODEL_VERSION",
    "OFFENSE_DEFENSE_ENABLED",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PROJECTION_MODEL_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_game_card",
    "_offense_defense_html",
    "_progress_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
