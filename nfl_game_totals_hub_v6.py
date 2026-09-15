"""NFL Game Totals V6 — Page Step 6 red-zone + drive sustainability.

Additive presentation layer over frozen Game Totals V5. V5 preserves the
verified slate, live FanDuel market, offense-vs-defense, pace/possession, and
explosive-scoring layers. V6 adds source-proven ESPN red-zone touchdown rate,
third-down conversion rate, and first-downs/game beneath the same matchup card.

The certified ESPN team-stat endpoint did not expose a trustworthy drive count.
Drive count remains unavailable; third-down conversion and first-down volume are
used as descriptive sustainability context only. Projection remains OFF and
sportsbook influence stays 0.0%.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v5 as v5
from sports_api.nfl_game_totals_red_zone_drive_context_v1 import (
    build_matchup_red_zone_drive_context,
    build_team_red_zone_drive_profile,
)

MODEL_VERSION = "NFL GAME TOTALS V6 • PAGE STEP 6 RED ZONE + DRIVE SUSTAINABILITY"
PAGE_BUILD_STEP = 6
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP6_CSS = r'''
<style>
.kgt-fill.step6{width:60%}
.kgt-rz{margin-top:9px;border:1px solid #5e3438;border-radius:12px;background:linear-gradient(180deg,#190f11,#100b0c);padding:9px}
.kgt-rz-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.kgt-rz-head b{font-size:.58rem;color:#ff9da7}.kgt-rz-head span{font-size:.44rem;color:#98747a;font-weight:850}
.kgt-rz-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kgt-rz-side{border:1px solid #3d2528;border-radius:10px;background:#100b0c;padding:8px}.kgt-rz-team{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:6px}.kgt-rz-team strong{font-size:.61rem;color:#f7f3ef}.kgt-rz-signal{font-size:.43rem;font-weight:950;border-radius:999px;padding:3px 6px;border:1px solid #6f5558;color:#d8bcc0}.kgt-rz-signal.high{border-color:#27775f;color:#7ef0bd;background:#10231d}.kgt-rz-signal.balanced{border-color:#7e6737;color:#f1cf83;background:#211c10}.kgt-rz-signal.low{border-color:#7a434d;color:#ff9daa;background:#281217}
.kgt-rz-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.kgt-rz-stat{border:1px solid #352124;border-radius:8px;padding:6px;background:#0c0809}.kgt-rz-stat span{display:block;font-size:.38rem;color:#927278;font-weight:900;letter-spacing:.03em}.kgt-rz-stat b{display:block;font-size:.72rem;color:#f4eeee;margin-top:2px}.kgt-rz-summary{margin-top:7px;border:1px solid #5a343a;border-radius:9px;padding:6px 8px;background:#170d0f;display:flex;justify-content:space-between;align-items:center;gap:8px}.kgt-rz-summary span{font-size:.43rem;color:#9d7b81}.kgt-rz-summary b{font-size:.54rem;color:#ff9da7}.kgt-rz-note{margin-top:6px;font-size:.42rem;color:#7d686c;line-height:1.35}.kgt-rz-unavailable{border-style:dashed}.kgt-rz-unavailable b{color:#ef9ca8}
@media(max-width:760px){.kgt-rz-grid{grid-template-columns:1fr}.kgt-rz-stats{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    return v5._safe(value, default)


def _fmt_pct(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:.1f}%" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _fmt(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:.1f}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _signal_class(signal: str) -> str:
    value = _safe(signal, "UNAVAILABLE").lower()
    return value if value in {"high", "balanced", "low"} else ""


def _red_zone_drive_html(context: dict[str, Any] | None) -> str:
    payload = context or {}
    if payload.get("ready") is not True:
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "ESPN red-zone/sustainability context unavailable.")
        return (
            '<div class="kgt-rz kgt-rz-unavailable">'
            '<div class="kgt-rz-head"><b>🔴 RED ZONE + DRIVE SUSTAINABILITY • STEP 6</b><span>DESCRIPTIVE ONLY</span></div>'
            f'<b>CONTEXT UNAVAILABLE</b><div class="kgt-rz-note">{escape(detail)} • Drive count unavailable from the certified ESPN team-stat endpoint.</div>'
            '</div>'
        )

    sides: list[str] = []
    for side in ("away", "home"):
        row = payload.get(side) or {}
        signal = _safe(row.get("signal"), "UNAVAILABLE").upper()
        sides.append(
            '<div class="kgt-rz-side">'
            '<div class="kgt-rz-team">'
            f'<strong>{escape(_safe(row.get("team"), row.get("abbr") or side.title()))}</strong>'
            f'<span class="kgt-rz-signal {_signal_class(signal)}">{escape(signal)}</span>'
            '</div>'
            '<div class="kgt-rz-stats">'
            '<div class="kgt-rz-stat"><span>RZ TD %</span>'
            f'<b>{escape(_fmt_pct(row.get("red_zone_td_pct")))}</b></div>'
            '<div class="kgt-rz-stat"><span>3RD DOWN %</span>'
            f'<b>{escape(_fmt_pct(row.get("third_down_conv_pct")))}</b></div>'
            '<div class="kgt-rz-stat"><span>1ST DOWNS/G</span>'
            f'<b>{escape(_fmt(row.get("first_downs_per_game")))}</b></div>'
            '</div></div>'
        )

    matchup = payload.get("matchup") or {}
    matchup_signal = _safe(matchup.get("signal"), "UNAVAILABLE").upper()
    return (
        '<div class="kgt-rz">'
        '<div class="kgt-rz-head"><b>🔴 RED ZONE + DRIVE SUSTAINABILITY • STEP 6</b><span>HIGH • BALANCED • LOW</span></div>'
        f'<div class="kgt-rz-grid">{"".join(sides)}</div>'
        '<div class="kgt-rz-summary">'
        f'<span>Matchup sustainability • RZ TD {_fmt_pct(matchup.get("average_red_zone_td_pct"))} • 3rd down {_fmt_pct(matchup.get("average_third_down_conv_pct"))} • 1st downs/G {_fmt(matchup.get("average_first_downs_per_game"))}</span>'
        f'<b>{escape(matchup_signal)}</b>'
        '</div>'
        '<div class="kgt-rz-note">Drive count unavailable from this certified ESPN team-stat endpoint; 3rd-down conversion and first-down volume represent drive sustainability • descriptive only • no FanDuel value enters this signal.</div>'
        '</div>'
    )


def _game_card(
    row: Any,
    snapshot: dict[str, Any] | None,
    scoring_context: dict[str, Any] | None,
    pace_context: dict[str, Any] | None,
    explosive_context: dict[str, Any] | None,
    red_zone_drive_context: dict[str, Any] | None,
) -> str:
    base_html = v5._game_card(row, snapshot, scoring_context, pace_context, explosive_context)
    section = _red_zone_drive_html(red_zone_drive_context)
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
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 6 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step6"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        v5.v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v5.v4.v3.v2._STEP2_CSS
        + v5.v4.v3._STEP3_CSS
        + v5.v4._STEP4_CSS
        + v5._STEP5_CSS
        + _STEP6_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 6 adds ESPN red-zone touchdown efficiency plus third-down and first-down sustainability beneath explosive scoring. Projection remains OFF and sportsbook influence stays 0.0%.</div>'
        + '<div class="kgt-chiprow"><span class="kgt-chip">EXACT ESPN GAME IDs</span><span class="kgt-chip teal">FANDUEL TOTAL LIVE</span><span class="kgt-chip teal">RZ + SUSTAINABILITY LIVE</span><span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span></div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN identity stays frozen.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + prices stay live.</span></div>'
        '<div class="kgt-tool live"><div class="icon">💥</div><b>Explosive Scoring</b><span>20+ yard volume remains connected.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🔴</div><b>Red Zone + Sustainability</b><span>RZ TD%, 3rd down%, and 1st downs/game are live.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 6 firewall:</strong> red-zone and sustainability context is descriptive only. '
        '<span class="orange">Projection remains OFF and sportsbook influence stays 0.0%.</span> '
        '<span class="teal">Drive count unavailable from the certified ESPN team-stat endpoint; no drive count is fabricated.</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=21600, show_spinner=False)
def _cached_red_zone_drive_profiles(day_str: str, team_rows: tuple[tuple[str, str], ...]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    unique = list(dict.fromkeys((str(abbr).upper(), str(name)) for abbr, name in team_rows if str(abbr).strip()))
    if not unique:
        return profiles
    with ThreadPoolExecutor(max_workers=min(8, len(unique))) as pool:
        futures = {pool.submit(build_team_red_zone_drive_profile, abbr, name, day_str): abbr for abbr, name in unique}
        for future in as_completed(futures):
            abbr = futures[future]
            try:
                profiles[abbr] = future.result()
            except Exception as exc:
                profiles[abbr] = {
                    "abbr": abbr,
                    "ready": False,
                    "drive_count_available": False,
                    "diagnostics": [str(exc)],
                    "descriptive_only": True,
                    "sportsbook_projection_weight": 0.0,
                }
    return profiles


def _red_zone_drive_contexts(games: pd.DataFrame, day_str: str) -> dict[str, dict[str, Any]]:
    if games.empty:
        return {}
    team_rows: list[tuple[str, str]] = []
    for _, row in games.iterrows():
        team_rows.extend([
            (_safe(row.get("away_abbr"), ""), _safe(row.get("away_team"), "Away")),
            (_safe(row.get("home_abbr"), ""), _safe(row.get("home_team"), "Home")),
        ])
    profiles = _cached_red_zone_drive_profiles(day_str, tuple(team_rows))
    output: dict[str, dict[str, Any]] = {}
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"), "")
        output[event_id] = build_matchup_red_zone_drive_context(
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
    st.markdown('<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals + Connected Context</h3><span>STEP 6 • CONNECTED</span></div>', unsafe_allow_html=True)
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("🎰 Loading live totals + ⚔️ scoring + ⏱️ pace + 💥 explosives + 🔴 red zone…"):
        snapshots = v5.v4.v3.v2._market_snapshots(games)
        scoring_contexts = v5.v4.v3._matchup_contexts(games, day_str)
        pace_contexts = v5.v4._pace_contexts(games, day_str)
        explosive_contexts = v5._explosive_contexts(games, day_str)
        red_zone_drive_contexts = _red_zone_drive_contexts(games, day_str)

    cards = "".join(
        _game_card(
            row,
            snapshots.get(_safe(row.get("game_id"), "")),
            scoring_contexts.get(_safe(row.get("game_id"), "")),
            pace_contexts.get(_safe(row.get("game_id"), "")),
            explosive_contexts.get(_safe(row.get("game_id"), "")),
            red_zone_drive_contexts.get(_safe(row.get("game_id"), "")),
        )
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    default_date = st.session_state.get(
        "nfl_game_totals_v6_date",
        st.session_state.get(
            "nfl_game_totals_v5_date",
            st.session_state.get(
                "nfl_game_totals_v4_date",
                st.session_state.get("nfl_game_totals_v3_date", st.session_state.get("nfl_v1_date", pd.Timestamp.now(tz=v5.v4.v3.v2.foundation.ET).date())),
            ),
        ),
    )
    selected = st.date_input("📅 NFL Game Totals slate date", value=default_date, key="nfl_game_totals_v6_date_input")
    for key in (
        "nfl_game_totals_v6_date", "nfl_game_totals_v5_date", "nfl_game_totals_v4_date",
        "nfl_game_totals_v3_date", "nfl_game_totals_v2_date", "nfl_game_totals_v1_date", "nfl_v1_date",
    ):
        st.session_state[key] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v5.v4.v3.v2.foundation.load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • projection OFF • live market ON • offense/defense ON • pace/possession ON • explosive scoring ON • red-zone/sustainability ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V6 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "EXPLOSIVE_SCORING_ENABLED",
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
    "_game_card",
    "_progress_html",
    "_red_zone_drive_contexts",
    "_red_zone_drive_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
