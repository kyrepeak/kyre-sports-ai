"""NFL Game Totals V2 — Page Step 2 live FanDuel total.

Additive presentation layer over frozen NFL Game Totals V1. V1 continues to own
verified ESPN slate identity, Phoenix kickoff display, matchup cards, and the
connected build language. V2 adds only the certified hosted FanDuel full-game
total snapshot keyed by the exact ESPN event ID already present on each card.

Projection math remains OFF. Sportsbook projection influence remains exactly
0.0%. Any transport, identity, contract, or market ambiguity fails closed.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v1 as foundation
from sports_api.nfl_game_totals_page_client_v1 import fetch_many_game_total_markets

MODEL_VERSION = "NFL GAME TOTALS V2 • PAGE STEP 2 LIVE FANDUEL TOTAL"
PAGE_BUILD_STEP = 2
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP2_CSS = r'''
<style>
.kgt-fill.step2{width:20%}
.kgt-market-live{border-style:solid!important;border-color:#755132!important;background:linear-gradient(180deg,#1c1510,#100f0d)!important;padding:9px!important}
.kgt-market-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.kgt-market-head b{color:#ffc180!important;font-size:.57rem!important}.kgt-market-state{border:1px solid #287b61;border-radius:999px;color:#7ff2c2;padding:3px 6px;font-size:.46rem;font-weight:950}.kgt-market-state.bad{border-color:#75414a;color:#ef9ca8}
.kgt-market-grid{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:6px;margin-top:7px}.kgt-market-stat{border:1px solid #3b3229;border-radius:9px;background:#120f0d;padding:7px;min-width:0}.kgt-market-stat span{display:block;color:#8e7967!important;font-size:.43rem!important;font-weight:900;letter-spacing:.05em}.kgt-market-stat b{display:block;color:#f9f4ef!important;font-size:.82rem!important;margin-top:2px}.kgt-market-stat.over b{color:#ffbc76!important}.kgt-market-stat.under b{color:#87e7ca!important}
.kgt-market-foot{display:grid;gap:2px;margin-top:7px;color:#6f7f89;font-size:.44rem;line-height:1.35}.kgt-market-foot strong{color:#a89789}.kgt-market-unavailable{border-style:dashed!important;border-color:#5d4650!important;background:#151014!important}.kgt-market-unavailable b{color:#ef9ca8!important}.kgt-market-unavailable span{color:#8d7880!important}
@media(max-width:760px){.kgt-market-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
'''

_MARKET_PLACEHOLDER = '<div class="market"><b>🎰 LIVE MARKET • STEP 2</b><span>Total / Over / Under prices connect next.</span></div>'


def _safe(value: Any, default: str = "—") -> str:
    return foundation._safe(value, default)


def _num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _american(value: Any) -> str:
    number = _num(value)
    if not math.isfinite(number):
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _total(value: Any) -> str:
    number = _num(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:.1f}"


def _compact_timestamp(value: Any) -> str:
    text = _safe(value, "—")
    if text == "—":
        return text
    return text.replace("+00:00", "Z")


def _market_html(snapshot: dict[str, Any] | None) -> str:
    payload = snapshot or {}
    ready = payload.get("ready") is True
    available = payload.get("market_available") is True
    markets = payload.get("markets") if isinstance(payload.get("markets"), list) else []
    if not (ready and available and len(markets) == 1):
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else []
        detail = _safe(diagnostics[0] if diagnostics else None, "Exact FanDuel total is not available for this ESPN event.")
        return (
            '<div class="market kgt-market-unavailable">'
            '<div class="kgt-market-head"><b>🎰 MARKET UNAVAILABLE</b><span class="kgt-market-state bad">FAIL CLOSED</span></div>'
            f'<span>{escape(detail)}</span>'
            '</div>'
        )

    market = markets[0] if isinstance(markets[0], dict) else {}
    provider_event_id = _safe(payload.get("provider_event_id"))
    captured_at_utc = _compact_timestamp(payload.get("captured_at_utc"))
    updated_at_utc = _compact_timestamp(market.get("updated_at_utc"))
    state = "ACTIVE" if market.get("active") is True else "UNAVAILABLE"
    state_class = "" if state == "ACTIVE" else " bad"
    return (
        '<div class="market kgt-market-live">'
        f'<div class="kgt-market-head"><b>🎰 FANDUEL • LIVE MARKET</b><span class="kgt-market-state{state_class}">{state}</span></div>'
        '<div class="kgt-market-grid">'
        f'<div class="kgt-market-stat"><span>TOTAL</span><b>{escape(_total(market.get("total")))}</b></div>'
        f'<div class="kgt-market-stat over"><span>OVER</span><b>{escape(_american(market.get("over_price")))}</b></div>'
        f'<div class="kgt-market-stat under"><span>UNDER</span><b>{escape(_american(market.get("under_price")))}</b></div>'
        '</div>'
        '<div class="kgt-market-foot">'
        f'<span>FanDuel event <strong>{escape(provider_event_id)}</strong> • market <strong>{escape(_safe(market.get("market_id")))}</strong></span>'
        f'<span>captured_at_utc {escape(captured_at_utc)}</span>'
        f'<span>updated_at_utc {escape(updated_at_utc)}</span>'
        '</div></div>'
    )


def _game_card(row: Any, snapshot: dict[str, Any] | None) -> str:
    base_html = foundation._game_card(row)
    return base_html.replace(_MARKET_PLACEHOLDER, _market_html(snapshot), 1)


def _progress_html() -> str:
    stages = (
        ("1", "VERIFIED SLATE", True),
        ("2", "LIVE TOTAL", True),
        ("3", "OFFENSE VS DEFENSE", False),
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
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 2 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step2"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        foundation._GAME_TOTALS_CSS
        + _STEP2_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 2 connects each verified ESPN matchup to the certified hosted FanDuel full-game total. The market is context only; projection remains OFF and sportsbook influence stays 0.0%.</div>'
        + '<div class="kgt-chiprow">'
        + '<span class="kgt-chip">EXACT ESPN GAME IDs</span>'
        + '<span class="kgt-chip teal">FANDUEL TOTAL LIVE</span>'
        + '<span class="kgt-chip teal">OVER / UNDER PRICES</span>'
        + '<span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span>'
        + '</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Step 1 exact ESPN identity stays frozen underneath.</span></div>'
        '<div class="kgt-tool live"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + Over/Under prices are identity-verified and active.</span></div>'
        '<div class="kgt-tool"><div class="icon">⚔️</div><b>Matchup Layers</b><span>Offense vs defense begins in Step 3.</span></div>'
        '<div class="kgt-tool"><div class="icon">🧠</div><b>Total Projection</b><span>TOTAL PROJECTION • STEP 8 — projection remains OFF.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 2 firewall:</strong> FanDuel is display/context only. '
        '<span class="orange">No market value enters projection math.</span> '
        '<span class="teal">Exact ESPN event ID is still the join key.</span> '
        'Any identity or market ambiguity displays MARKET UNAVAILABLE.</div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=45, show_spinner=False)
def _cached_market_batch(event_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return fetch_many_game_total_markets(event_ids)


def _market_snapshots(games: pd.DataFrame) -> dict[str, dict[str, Any]]:
    event_ids: list[str] = []
    if games.empty:
        return {}
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"), "")
        state = _safe(row.get("state"), "pre").lower()
        if event_id.isdigit() and state == "pre":
            event_ids.append(event_id)
    return _cached_market_batch(tuple(event_ids)) if event_ids else {}


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
        f"✅ Verified NFL schedule • {day_str} • ESPN identity + certified FanDuel market API • {len(games)} game(s) • "
        "kickoff clocks displayed in Phoenix MST"
    )
    st.markdown(
        '<div class="kgt-section"><h3>🏟️ Verified Matchups + Live Totals</h3><span>STEP 2 • EXACT ESPN → FANDUEL</span></div>',
        unsafe_allow_html=True,
    )
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    with st.spinner("🎰 Loading exact FanDuel full-game totals…"):
        snapshots = _market_snapshots(games)
    cards = "".join(
        _game_card(row, snapshots.get(_safe(row.get("game_id"), "")))
        for _, row in games.iterrows()
    )
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()

    default_date = st.session_state.get(
        "nfl_game_totals_v2_date",
        st.session_state.get("nfl_game_totals_v1_date", st.session_state.get("nfl_v1_date", pd.Timestamp.now(tz=foundation.ET).date())),
    )
    selected = st.date_input(
        "📅 NFL Game Totals slate date",
        value=default_date,
        key="nfl_game_totals_v2_date_input",
    )
    st.session_state["nfl_game_totals_v2_date"] = selected
    st.session_state["nfl_game_totals_v1_date"] = selected
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = foundation.load_nfl_slate(day_str)

    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • "
        "projection OFF • live market ON • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V2 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "LIVE_MARKET_ENABLED",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PROJECTION_MODEL_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_game_card",
    "_market_html",
    "_progress_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
