"""NFL Spread V1 — verified slate + certified Kyre Sports API market context.

Step 5 transport/presentation layer only. The page joins the frozen verified NFL
slate to the certified Spread API strictly by official ESPN event ID. Projection,
Monte Carlo, grading, rankings, stake sizing, and wager actions remain OFF.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

import nfl_hub_v1 as base
import nfl_spread_market_api_v1 as market_api

MODEL_VERSION = "NFL SPREAD V1 • KYRE SPORTS API CONNECTED • MODEL OFF"
FROZEN_SLATE_OWNER = "nfl_hub_v1"
MARKET_OWNER = "nfl_spread_market_api_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
MAX_MARKET_WORKERS = 6


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _logo(url: Any, abbr: Any, name: Any) -> str:
    src = _safe(url)
    if src:
        return (
            f'<img class="kspread-logo" src="{escape(src, quote=True)}" '
            f'alt="{escape(_safe(name, "NFL team"), quote=True)} logo" loading="lazy">'
        )
    return f'<div class="kspread-logo-fallback">{escape(_safe(abbr, "NFL")[:4])}</div>'


def _age_text(value: Any) -> str:
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return "fresh"
    if seconds < 60:
        return f"{seconds}s old"
    return f"{seconds // 60}m old"


def _identity_matches_game(game: dict[str, Any], market: dict[str, Any]) -> bool:
    identity = market.get("identity") or {}
    if not isinstance(identity, dict):
        return False
    return (
        _safe(market.get("official_event_id")) == _safe(game.get("game_id"))
        and _safe(identity.get("official_event_id")) == _safe(game.get("game_id"))
        and _safe(identity.get("away_abbr")).upper() == _safe(game.get("away_abbr")).upper()
        and _safe(identity.get("home_abbr")).upper() == _safe(game.get("home_abbr")).upper()
        and identity.get("fuzzy_matching") is False
        and identity.get("synthetic_event_ids") is False
        and market.get("projection_weight") == 0.0
    )


def _fetch_one(game: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    event_id = _safe(game.get("game_id"))
    if not event_id.isdigit():
        return event_id, {
            "ready": False,
            "reason": "Verified slate did not provide a numeric official ESPN event ID.",
            "books": [],
            "projection_weight": 0.0,
        }
    market = market_api.fetch_event_market(event_id)
    if market.get("ready") and not _identity_matches_game(game, market):
        market = {
            "ready": False,
            "market_available": False,
            "reason": "Spread API identity did not match the verified ESPN slate; market failed closed.",
            "official_event_id": event_id,
            "books": [],
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "model_probability_input": False,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        }
    return event_id, market


def _fetch_markets(games: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if games is None or games.empty:
        return {}
    pregame = [row.to_dict() for _, row in games.iterrows() if _safe(row.get("state")).lower() == "pre"]
    if not pregame:
        return {}
    out: dict[str, dict[str, Any]] = {}
    workers = min(MAX_MARKET_WORKERS, max(1, len(pregame)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nfl-spread-market") as pool:
        futures = [pool.submit(_fetch_one, game) for game in pregame]
        for future in as_completed(futures):
            try:
                event_id, market = future.result()
            except Exception as exc:
                event_id = ""
                market = {
                    "ready": False,
                    "reason": f"Spread API client failed closed: {type(exc).__name__}",
                    "books": [],
                    "projection_weight": 0.0,
                }
            if event_id:
                out[event_id] = market
    return out


def _market_panel(game: dict[str, Any], market: dict[str, Any]) -> str:
    event_id = _safe(game.get("game_id"))
    state = _safe(game.get("state"), "pre").lower()
    ready = bool(market.get("ready")) if state == "pre" else False
    books = market.get("books") or [] if ready else []
    book = books[0] if books else {}

    away_spread = market_api.fmt_spread(book.get("away_spread")) if book else "—"
    home_spread = market_api.fmt_spread(book.get("home_spread")) if book else "—"
    away_price = market_api.fmt_american(book.get("away_price")) if book else "—"
    home_price = market_api.fmt_american(book.get("home_price")) if book else "—"
    sportsbook = _safe(book.get("sportsbook"), "FanDuel" if ready else "Market unavailable")
    freshness = _age_text(book.get("age_seconds")) if book else ""

    if state != "pre":
        status_copy = "Pregame spread transport is intentionally disabled after kickoff."
        status_class = "off"
    elif ready:
        status_copy = f"{sportsbook} • active • {freshness}"
        status_class = "live"
    else:
        status_copy = _safe(market.get("reason"), "Certified pregame spread is unavailable.")
        status_class = "off"

    return f'''
    <article class="kspread-card" data-event-id="{escape(event_id, quote=True)}">
      <div class="kspread-top">
        <span>{escape(_safe(game.get('season_type'), 'NFL'))}</span>
        <span>{escape(_safe(game.get('tip_et'), 'TBD'))}</span>
      </div>
      <div class="kspread-team">
        {_logo(game.get('away_logo'), game.get('away_abbr'), game.get('away_team'))}
        <div class="kspread-teamcopy"><b>{escape(_safe(game.get('away_team'), 'Away'))}</b><small>{escape(_safe(game.get('away_record'), '—'))}</small></div>
        <div class="kspread-line"><strong>{escape(away_spread)}</strong><span>{escape(away_price)}</span></div>
      </div>
      <div class="kspread-at">AT</div>
      <div class="kspread-team">
        {_logo(game.get('home_logo'), game.get('home_abbr'), game.get('home_team'))}
        <div class="kspread-teamcopy"><b>{escape(_safe(game.get('home_team'), 'Home'))}</b><small>{escape(_safe(game.get('home_record'), '—'))}</small></div>
        <div class="kspread-line"><strong>{escape(home_spread)}</strong><span>{escape(home_price)}</span></div>
      </div>
      <div class="kspread-status {status_class}">{escape(status_copy)}</div>
      <div class="kspread-meta">
        <span>🏟️ {escape(_safe(game.get('venue'), 'Venue TBD'))}</span>
        <span>📺 {escape(_safe(game.get('broadcast'), '—'))}</span>
        <span>🆔 ESPN {escape(event_id)}</span>
      </div>
    </article>
    '''


_CSS = r'''
<style>
.kspread-hero{border:1px solid rgba(56,189,248,.28);border-radius:20px;background:linear-gradient(135deg,rgba(14,165,233,.14),rgba(15,23,42,.96));padding:17px 18px;margin:8px 0 16px}.kspread-eyebrow{font-size:.68rem;font-weight:950;letter-spacing:.12em;color:#7dd3fc;text-transform:uppercase}.kspread-title{font-size:1.65rem;font-weight:950;color:#f8fafc;margin-top:3px}.kspread-sub{font-size:.76rem;line-height:1.5;color:#94a3b8;margin-top:5px}.kspread-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:11px}.kspread-chip{font-size:.58rem;font-weight:900;color:#bae6fd;border:1px solid rgba(56,189,248,.25);border-radius:999px;padding:5px 8px;background:rgba(2,132,199,.08)}
.kspread-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}.kspread-card{border:1px solid rgba(71,85,105,.58);border-radius:17px;background:linear-gradient(180deg,#0d1726,#09111d);padding:13px;min-width:0;box-shadow:0 10px 28px rgba(0,0,0,.12)}.kspread-top{display:flex;justify-content:space-between;gap:10px;color:#7f96ad;font-size:.58rem;font-weight:900;text-transform:uppercase}.kspread-team{display:flex;align-items:center;gap:9px;margin-top:11px}.kspread-logo{width:44px;height:44px;object-fit:contain;flex:0 0 44px}.kspread-logo-fallback{width:44px;height:44px;border-radius:50%;border:1px solid #365069;display:flex;align-items:center;justify-content:center;color:#9fb4c8;font-size:.55rem;font-weight:950;flex:0 0 44px}.kspread-teamcopy{display:flex;flex-direction:column;min-width:0;flex:1}.kspread-teamcopy b{color:#f8fafc;font-size:.84rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kspread-teamcopy small{color:#71869b;font-size:.58rem;margin-top:2px}.kspread-line{display:flex;flex-direction:column;align-items:flex-end;min-width:64px}.kspread-line strong{color:#7dd3fc;font-size:1.22rem}.kspread-line span{color:#94a3b8;font-size:.63rem;font-weight:800}.kspread-at{font-size:.48rem;color:#526b82;font-weight:950;margin:2px 0 0 53px}.kspread-status{margin-top:11px;border-radius:10px;padding:7px 9px;font-size:.61rem;font-weight:850}.kspread-status.live{color:#86efac;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2)}.kspread-status.off{color:#fda4af;background:rgba(244,63,94,.07);border:1px solid rgba(244,63,94,.18)}.kspread-meta{display:grid;gap:3px;border-top:1px solid rgba(51,65,85,.55);margin-top:9px;padding-top:8px;color:#71869b;font-size:.55rem}
@media(max-width:700px){.kspread-grid{grid-template-columns:1fr}.kspread-title{font-size:1.4rem}}
</style>
'''


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V1 only owns the Spread route.")

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="kspread-hero">'
        '<div class="kspread-eyebrow">NFL • certified market transport</div>'
        '<div class="kspread-title">🎯 NFL Spread</div>'
        '<div class="kspread-sub">Verified ESPN schedule joined to the certified Kyre Sports API by official event ID only. Live sportsbook lines are visible market context; projection, Monte Carlo, grading, rankings, staking and wager actions remain OFF in Step 5.</div>'
        '<div class="kspread-chips">'
        '<span class="kspread-chip">KYRE SPORTS API</span>'
        '<span class="kspread-chip">FANDUEL</span>'
        '<span class="kspread-chip">EXACT ESPN ID</span>'
        '<span class="kspread-chip">MODEL OFF</span>'
        '<span class="kspread-chip">PROJECTION INFLUENCE 0.0%</span>'
        '</div></section>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(base.ET).date()
    selected = st.date_input(
        "📅 NFL Spread date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_spread_v1_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL slate…"):
        games, diag = base.load_nfl_slate(day_str)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. Spread stays fail-closed and no fake games or lines are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        return

    with st.spinner("🔌 Connecting certified NFL Spread markets…"):
        markets = _fetch_markets(games)

    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    available = sum(1 for market in markets.values() if market.get("ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", int(len(games)))
    c2.metric("Upcoming", upcoming)
    c3.metric("Live spreads", available)
    c4.metric("Model", "OFF")

    st.caption(
        f"✅ Verified NFL schedule • {day_str} • {diag.get('provider')} • {len(games)} game(s) • "
        f"{available}/{upcoming} pregame Spread market(s) certified • sportsbook projection influence 0.0%"
    )

    if games.empty:
        st.info("No verified NFL games were returned for this date.")
        return

    cards = []
    for _, row in games.iterrows():
        game = row.to_dict()
        event_id = _safe(game.get("game_id"))
        market_state = markets.get(event_id) or {
            "ready": False,
            "reason": "Pregame Spread market was not requested for this game state.",
            "books": [],
            "projection_weight": 0.0,
        }
        cards.append(_market_panel(game, market_state))
    st.markdown('<div class="kspread-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    with st.expander("🔒 Spread transport contract", expanded=False):
        st.write(
            {
                "page_version": MODEL_VERSION,
                "verified_slate_owner": FROZEN_SLATE_OWNER,
                "market_owner": MARKET_OWNER,
                "official_event_identity": "ESPN game_id only",
                "fuzzy_matching": False,
                "synthetic_event_ids": False,
                "sportsbook_projection_influence": 0.0,
                "projection_model": "OFF",
                "monte_carlo": "OFF",
                "rankings_recommendations": "OFF",
                "stake_sizing": "OFF",
                "wager_actions": "OFF",
            }
        )


__all__ = [
    "FROZEN_SLATE_OWNER",
    "MARKET_OWNER",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "render_nfl_hub",
]
