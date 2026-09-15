"""NFL Game Totals V5 — Page Step 5 explosive scoring context.

Additive presentation layer over frozen Game Totals V4. V4 keeps verified slate,
live FanDuel market, offense-vs-defense, and pace/possession. V5 adds descriptive
20+ yard explosive-play pressure beneath the same matchup card.

Projection remains OFF. Sportsbook influence remains exactly 0.0%.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v4 as v4
from sports_api.nfl_game_totals_explosive_context_v1 import (
    build_matchup_explosive_context,
    build_team_explosive_profile,
)

MODEL_VERSION = "NFL GAME TOTALS V5 • PAGE STEP 5 EXPLOSIVE SCORING"
PAGE_BUILD_STEP = 5
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP5_CSS = r'''
<style>
.kgt-fill.step5{width:50%}
.kgt-boom{margin-top:9px;border:1px solid #59432f;border-radius:12px;background:linear-gradient(180deg,#18120e,#100d0b);padding:9px}
.kgt-boom-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.kgt-boom-head b{font-size:.58rem;color:#ffc27d}.kgt-boom-head span{font-size:.44rem;color:#8b796b;font-weight:850}
.kgt-boom-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kgt-boom-side{border:1px solid #3a2e25;border-radius:10px;background:#100d0b;padding:8px}.kgt-boom-team{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:6px}.kgt-boom-team strong{font-size:.61rem;color:#f7f3ef}.kgt-boom-signal{font-size:.43rem;font-weight:950;border-radius:999px;padding:3px 6px;border:1px solid #6f5c47;color:#d9c2a7}.kgt-boom-signal.favorable{border-color:#27775f;color:#7ef0bd;background:#10231d}.kgt-boom-signal.medium{border-color:#7e6737;color:#f1cf83;background:#211c10}.kgt-boom-signal.tough{border-color:#7b3d48;color:#f2a0aa;background:#211216}
.kgt-boom-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.kgt-boom-stat{border:1px solid #332820;border-radius:8px;padding:6px;background:#0c0a08}.kgt-boom-stat span{display:block;font-size:.38rem;color:#8d7968;font-weight:900;letter-spacing:.03em}.kgt-boom-stat b{display:block;font-size:.72rem;color:#f4eee8;margin-top:2px}.kgt-boom-summary{margin-top:7px;border:1px solid #57402d;border-radius:9px;padding:6px 8px;background:#17100c;display:flex;justify-content:space-between;align-items:center;gap:8px}.kgt-boom-summary span{font-size:.43rem;color:#9b8370}.kgt-boom-summary b{font-size:.54rem;color:#ffc27d}.kgt-boom-note{margin-top:6px;font-size:.42rem;color:#77685d;line-height:1.35}.kgt-boom-unavailable{border-style:dashed}.kgt-boom-unavailable b{color:#ef9ca8}
@media(max-width:760px){.kgt-boom-grid{grid-template-columns:1fr}.kgt-boom-stats{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v4._safe(value, default)


def _fmt(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:.1f}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _count(value: Any) -> str:
    try:
        number = float(value)
        if not math.isfinite(number):
            return "—"
        return str(int(round(number)))
    except (TypeError, ValueError):
        return "—"


def _signal_class(signal: str) -> str:
    value = _safe(signal, "UNAVAILABLE").lower()
    return value if value in {"favorable", "medium", "tough"} else ""


def _explosive_html(context: dict[str, Any] | None) -> str:
    payload = context or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "ESPN explosive-play context unavailable.")
        return (
            '<div class="kgt-boom kgt-boom-unavailable">'
            '<div class="kgt-boom-head"><b>💥 EXPLOSIVE SCORING • STEP 5</b><span>DESCRIPTIVE ONLY</span></div>'
            f'<b>CONTEXT UNAVAILABLE</b><div class="kgt-boom-note">{escape(detail)}</div>'
            '</div>'
        )

    sides: list[str] = []
    for side in ("away", "home"):
        row = payload.get(side) or {}
        signal = _safe(row.get("signal"), "UNAVAILABLE").upper()
        sides.append(
            '<div class="kgt-boom-side">'
            '<div class="kgt-boom-team">'
            f'<strong>{escape(_safe(row.get("team"), row.get("abbr") or side.title()))}</strong>'
            f'<span class="kgt-boom-signal {_signal_class(signal)}">{escape(signal)}</span>'
            '</div>'
            '<div class="kgt-boom-stats">'
            '<div class="kgt-boom-stat"><span>20+ RUSH</span>'
            f'<b>{escape(_count(row.get("rushing_big_plays")))}</b></div>'
            '<div class="kgt-boom-stat"><span>20+ RECEIVE</span>'
            f'<b>{escape(_count(row.get("receiving_big_plays")))}</b></div>'
            '<div class="kgt-boom-stat"><span>EXPLOSIVE / 100 PLAYS</span>'
            f'<b>{escape(_fmt(row.get("explosive_plays_per_100")))}</b></div>'
            '</div></div>'
        )

    matchup = payload.get("matchup") or {}
    matchup_signal = _safe(matchup.get("signal"), "UNAVAILABLE").upper()
    return (
        '<div class="kgt-boom">'
        '<div class="kgt-boom-head"><b>💥 EXPLOSIVE SCORING • STEP 5</b><span>FAVORABLE • MEDIUM • TOUGH</span></div>'
        f'<div class="kgt-boom-grid">{"".join(sides)}</div>'
        '<div class="kgt-boom-summary">'
        f'<span>Matchup explosive pressure • avg {_fmt(matchup.get("average_explosive_plays_per_100"))} big plays / 100 offensive plays</span>'
        f'<b>{escape(matchup_signal)}</b>'
        '</div>'
        '<div class="kgt-boom-note">ESPN 20+ yard rushing + receiving big plays normalized by offensive plays • descriptive only • no FanDuel value enters this signal.</div>'
        '</div>'
    )


def _game_card(
    row: Any,
    snapshot: dict[str, Any] | None,
    scoring_context: dict[str, Any] | None,
    pace_context: dict[str, Any] | None,
    explosive_context: dict[str, Any] | None,
) -> str:
    base_html = v4._game_card(row, snapshot, scoring_context, pace_context)
    section = _explosive_html(explosive_context)
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
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 5 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill" style="width:50%"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v4.v3.v2._STEP2_CSS
        + v4.v3._STEP3_CSS
        + v4._STEP4_CSS
        + _STEP5_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 5 adds 20+ yard explosive-play pressure beneath pace and possession. The signal is descriptive only; projection remains OFF and sportsbook influence stays 0.0%.</div>'
        + '<div class="kgt-chiprow"><span class="kgt-chip">EXACT ESPN GAME IDs</span><span class="kgt-chip teal">FANDUEL TOTAL LIVE</span><span class="kgt-chip teal">OFF/DEF LIVE</span><span class="kgt-chip teal">PACE LIVE</span><span class="kgt-chip teal">EXPLOSIVES LIVE</span><span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span></div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN identity stays frozen.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + prices stay live.</span></div>'
        '<div class="kgt-tool live"><div class="icon">⏱️</div><b>Pace + Possession</b><span>Opportunity volume stays connected.</span></div>'
        '<div class="kgt-tool live"><div class="icon">💥</div><b>Explosive Scoring</b><span>20+ yard rushing and receiving pressure is live.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 5 firewall:</strong> explosive-play pressure is descriptive only. '
        '<span class="orange">Projection remains OFF and sportsbook influence stays 0.0%.</span> '
        '<span class="teal">The same matchup card keeps growing downward.</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=21600, show_spinner=False)
def _cached_explosive_profiles(day_str: str, team_rows: tuple[tuple[str, str], ...]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    unique = list(dict.fromkeys((str(abbr).upper(), str(name)) for abbr, name in team_rows if str(abbr).strip()))
    if not unique:
        return profiles
    with ThreadPoolExecutor(max_workers=min(8, len(unique))) as pool:
        futures = {
            pool.submit(build_team_explosive_profile, abbr, name, day_str): abbr
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


def _explosive_contexts(games: pd.DataFrame, day_str: str) -> dict[str, dict[str, Any]]:
    if games.empty:
        return {}
    team_rows: list[tuple[str, str]] = []
    for _, row in games.iterrows():
        team_rows.extend([
            (_safe(row.get("away_abbr"), ""), _safe(row.get("away_team"), "Away")),
            (_safe(row.get("home_abbr"), ""), _safe(row.get("home_team"), "Home")),
        ])
    profiles = _cached_explosive_profiles(day_str, tuple(team_rows))
    output: dict[str, dict[str, Any]] = {}
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"), "")
        output[event_id] = build_matchup_explosive_context(
            _safe(row.get("away_abbr"), ""), _safe(row.get("away_team"), "Away"),
            _safe(row.get("home_abbr"), ""), _safe(row.get("home_team"), "Home"),
            day_str, profiles=profiles,
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
    st.caption(f"✅ Verified NFL schedule • {day_str} • connected ESPN context + certified FanDuel market API • {len(games)} game(s) • kickoff clocks displayed in Phoenix MST")
    st.markdown('<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals + Connected Context</h3><span>STEP 5 • CONNECTED</span></div>', unsafe_allow_html=True)
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return
    with st.spinner("🎰 Loading live totals + ⚔️ scoring + ⏱️ pace + 💥 explosives…"):
        snapshots = v4.v3.v2._market_snapshots(games)
        scoring_contexts = v4.v3._matchup_contexts(games, day_str)
        pace_contexts = v4._pace_contexts(games, day_str)
        explosive_contexts = _explosive_contexts(games, day_str)
    cards = "".join(
        _game_card(
            row,
            snapshots.get(_safe(row.get("game_id"), "")),
            scoring_contexts.get(_safe(row.get("game_id"), "")),
            pace_contexts.get(_safe(row.get("game_id"), "")),
            explosive_contexts.get(_safe(row.get("game_id"), "")),
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    default_date = st.session_state.get("nfl_game_totals_v5_date", st.session_state.get("nfl_game_totals_v4_date", pd.Timestamp.now(tz=v4.v3.v2.foundation.ET).date()))
    selected = st.date_input("📅 NFL Game Totals slate date", value=default_date, key="nfl_game_totals_v5_date_input")
    for key in ("nfl_game_totals_v5_date", "nfl_game_totals_v4_date", "nfl_game_totals_v3_date", "nfl_game_totals_v2_date", "nfl_game_totals_v1_date", "nfl_v1_date"):
        st.session_state[key] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v4.v3.v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    st.caption(f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • projection OFF • live market ON • explosive scoring context ON • wager actions OFF")


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V5 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "EXPLOSIVE_SCORING_ENABLED", "LIVE_MARKET_ENABLED", "MODEL_VERSION", "OFFENSE_DEFENSE_ENABLED",
    "PACE_POSSESSION_ENABLED", "PAGE_BUILD_STEP", "PAGE_BUILD_TOTAL", "PROJECTION_MODEL_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED",
    "_explosive_html", "_game_card", "_progress_html", "render_nfl_game_totals_hub", "render_nfl_hub",
]
