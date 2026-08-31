"""MLB Moneyline V16.4 — Step 7C API market-context presentation.

This wrapper keeps the existing V16.3/V16.2/V16.1/V16 Moneyline model chain
intact and adds one read-only exact-ID FanDuel Moneyline snapshot immediately
above the existing Top-5 scanner cards. The Kyre Sports API is presentation
context only: no live price changes projection, simulation, win probability,
history adjustment, ranking, selection, or fair odds.

If API transport, contract, identity, price, or freshness cannot be proven,
V16.3 renders normally with no synthetic market evidence.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import requests
import streamlit as st

import mlb_moneyline_hub_v163 as prior
from sports_api.mlb_step7c_moneyline_api_integration_v1 import (
    API_CONNECTED,
    FALLBACK,
    build_moneyline_api_state,
    enforce_moneyline_api_freshness,
    moneyline_api_context_for_result,
)

MODEL_VERSION = "V16.4 • STEP 7C • EXACT-ID FANDUEL MONEYLINE API CONTEXT"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
_STATE_KEY = "mlb_step7c_moneyline_api_integration_v1"


def _api_base_url() -> str:
    value = (
        os.getenv("KYRE_SPORTS_API_BASE_URL")
        or os.getenv("SPORTS_API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )
    return str(value).strip().rstrip("/")


@st.cache_data(ttl=30, show_spinner=False)
def _cached_moneyline_api_state(base_url: str) -> dict[str, Any]:
    root = str(base_url or "").strip().rstrip("/")
    if not root:
        return {
            "data_type": "mlb_step7c_moneyline_api_integration_v1",
            "schema_version": 1,
            "integration_status": FALLBACK,
            "api_integration_active": False,
            "frozen_moneyline_fallback_preserved": True,
            "failures": ["api_base_url_empty"],
        }
    try:
        response = requests.get(
            f"{root}/api/v1/mlb/odds",
            params={"max_events": 30, "fully_priced_only": "true"},
            timeout=25,
            headers={
                "Accept": "application/json",
                "User-Agent": "KyreSportsMLBMoneylineStep7C/1.0",
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        state = enforce_moneyline_api_freshness(build_moneyline_api_state(response.json()))
        state["http_status"] = int(response.status_code)
        return state
    except Exception as exc:
        return {
            "data_type": "mlb_step7c_moneyline_api_integration_v1",
            "schema_version": 1,
            "integration_status": FALLBACK,
            "api_integration_active": False,
            "source": "FanDuel",
            "match_method": "official_mlb_game_id_exact",
            "fallback_matching_used": False,
            "feed_fresh": False,
            "frozen_moneyline_fallback_preserved": True,
            "model_math_impact": False,
            "simulation_impact": False,
            "probability_impact": False,
            "history_adjustment_impact": False,
            "ranking_impact": False,
            "selection_impact": False,
            "fair_odds_impact": False,
            "sportsbook_price_model_input": False,
            "production_exposure_impact": False,
            "wagering_impact": False,
            "durable_persistence": False,
            "wnba_impact": False,
            "failures": [f"transport_or_contract_error:{type(exc).__name__}"],
        }


def _odds(value: Any) -> str:
    try:
        number = int(value)
    except Exception:
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _market_strip_html(results: list[Mapping[str, Any]], state: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for rank, result in enumerate(list(results or [])[:5], 1):
        context = moneyline_api_context_for_result(result, state)
        team = escape(str(result.get("team") or "Selected side"))
        game_id = escape(str(result.get("game_pk") or "—"))
        fair = escape(str(result.get("fair_odds") or "—"))
        if context is None:
            rows.append(
                '<div class="ks164-row">'
                f'<span>#{rank} {team}</span><span>MLB {game_id}</span>'
                '<strong>API CONTEXT UNAVAILABLE</strong>'
                f'<em>Model fair {fair} • frozen V16.3 card unchanged</em>'
                '</div>'
            )
            continue

        rows.append(
            '<div class="ks164-row">'
            f'<span>#{rank} {team}</span><span>MLB {context["official_game_id"]}</span>'
            f'<strong>FanDuel {_odds(context["live_fanduel_odds"])}</strong>'
            f'<em>Model fair {fair} • display only</em>'
            '</div>'
        )

    collected = escape(str(state.get("collected_at_utc") or "timestamp unavailable"))
    age = state.get("snapshot_age_seconds")
    age_text = f"{float(age):.1f}s old" if isinstance(age, (int, float)) else "age unavailable"
    status = escape(str(state.get("integration_status") or FALLBACK).replace("_", " "))
    return (
        '<style>'
        '.ks164-board{margin:8px 0 10px;border:1px solid #31506a;background:#07121d;border-radius:12px;padding:9px}'
        '.ks164-head{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:.52rem;font-weight:950;color:#9bd6ff;margin-bottom:6px}'
        '.ks164-row{display:grid;grid-template-columns:1.3fr .65fr .9fr 1.35fr;gap:7px;align-items:center;padding:6px 5px;border-top:1px solid rgba(80,125,155,.2);font-size:.48rem;color:#b9ccd9}'
        '.ks164-row strong{color:#f5fbff}.ks164-row em{font-style:normal;font-weight:800;color:#8da5b5}'
        '.ks164-foot{font-size:.42rem;color:#71899a;line-height:1.45;margin-top:6px}'
        '@media(max-width:640px){.ks164-row{grid-template-columns:1.2fr .7fr 1fr}.ks164-row em{grid-column:1/-1}}'
        '</style>'
        '<div class="ks164-board">'
        '<div class="ks164-head"><span>STEP 7C • LIVE FANDUEL MONEYLINE • EXACT MLB GAME ID</span>'
        f'<span>{status}</span></div>'
        + "".join(rows)
        + f'<div class="ks164-foot">Snapshot {collected} • {escape(age_text)} • display-only API context. '
        'FanDuel price is never substituted into the frozen V16.3 model. '
        'No API evidence changes projection, probability, simulation, H2H adjustment, ranking, selection, or fair odds.</div></div>'
    )


def _render_api_market_strip(results, status_info, team_logo, h, *, state):
    st.markdown(_market_strip_html(list(results or []), state), unsafe_allow_html=True)


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render V16.3 unchanged, with an additive exact-ID API Moneyline strip."""
    state = _cached_moneyline_api_state(_api_base_url())
    st.session_state[_STATE_KEY] = dict(state)

    if state.get("integration_status") != API_CONNECTED:
        st.caption(
            "⚪ MLB Moneyline Step 7C • API market context unavailable, so the frozen V16.3 Moneyline presentation remains authoritative and unchanged."
        )
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)

    v161 = prior.base.base
    frozen_cards = v161._render_cards_v161

    def cards_with_api_context(results, status_info_inner, team_logo_inner, h_inner):
        _render_api_market_strip(
            results,
            status_info_inner,
            team_logo_inner,
            h_inner,
            state=state,
        )
        return frozen_cards(results, status_info_inner, team_logo_inner, h_inner)

    v161._render_cards_v161 = cards_with_api_context
    try:
        st.caption(
            "🔗 MLB Moneyline Step 7C • Kyre Sports API exact-ID FanDuel Moneyline context is active above the existing Top-5 cards • model math unchanged."
        )
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        v161._render_cards_v161 = frozen_cards


__all__ = [
    "DEFAULT_API_BASE_URL",
    "MODEL_VERSION",
    "render_moneyline_hub",
]
