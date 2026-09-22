"""MLB Spread / Run Line V15.7 — Step 7B API market-context presentation.

This wrapper keeps the existing V15.6.4 Spread model/presentation chain intact
and adds one read-only exact-ID FanDuel Run Line snapshot immediately above the
existing Top-5 cards. The Kyre Sports API is presentation context only: no live
price changes projection, simulation, cover probability, history adjustment,
ranking, selection, fair odds, or any other model output.

If the API request, contract, or snapshot freshness cannot be proven, V15.6.4
renders normally.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import requests
import streamlit as st

import mlb_spread_hub_v156 as prior
from sports_api.mlb_step7b_spread_api_integration_v1 import (
    API_CONNECTED,
    FALLBACK,
    build_spread_api_state,
    enforce_spread_api_freshness,
    spread_api_context_for_result,
)

MODEL_VERSION = "V15.7 • STEP 7B • EXACT-ID FANDUEL RUN LINE API CONTEXT"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
_STATE_KEY = "mlb_step7b_spread_api_integration_v1"


def _api_base_url() -> str:
    value = (
        os.getenv("KYRE_SPORTS_API_BASE_URL")
        or os.getenv("SPORTS_API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )
    return str(value).strip().rstrip("/")


@st.cache_data(ttl=30, show_spinner=False)
def _cached_spread_api_state(base_url: str) -> dict[str, Any]:
    root = str(base_url or "").strip().rstrip("/")
    if not root:
        return {
            "data_type": "mlb_step7b_spread_api_integration_v1",
            "schema_version": 1,
            "integration_status": FALLBACK,
            "api_integration_active": False,
            "frozen_spread_fallback_preserved": True,
            "failures": ["api_base_url_empty"],
        }
    try:
        response = requests.get(
            f"{root}/api/v1/mlb/odds",
            params={"max_events": 30, "fully_priced_only": "true"},
            timeout=25,
            headers={
                "Accept": "application/json",
                "User-Agent": "KyreSportsMLBSpreadStep7B/1.0",
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        state = enforce_spread_api_freshness(build_spread_api_state(response.json()))
        state["http_status"] = int(response.status_code)
        return state
    except Exception as exc:
        return {
            "data_type": "mlb_step7b_spread_api_integration_v1",
            "schema_version": 1,
            "integration_status": FALLBACK,
            "api_integration_active": False,
            "source": "FanDuel",
            "match_method": "official_mlb_game_id_exact",
            "fallback_matching_used": False,
            "feed_fresh": False,
            "frozen_spread_fallback_preserved": True,
            "model_math_impact": False,
            "simulation_impact": False,
            "probability_impact": False,
            "history_adjustment_impact": False,
            "ranking_impact": False,
            "selection_impact": False,
            "fair_odds_impact": False,
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


def _line(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    return f"{number:+.1f}"


def _market_strip_html(results: list[Mapping[str, Any]], state: Mapping[str, Any], h) -> str:
    rows: list[str] = []
    for rank, result in enumerate(list(results or [])[:5], 1):
        context = spread_api_context_for_result(result, state)
        team = escape(str(result.get("team") or "Selected side"))
        game_id = escape(str(result.get("game_pk") or "—"))
        if context is None:
            rows.append(
                '<div class="ks157-row">'
                f'<span>#{rank} {team}</span><span>MLB {game_id}</span>'
                '<strong>API CONTEXT UNAVAILABLE</strong>'
                '<em>Frozen V15.6 model/card unchanged</em>'
                '</div>'
            )
            continue

        same_line = context.get("line_match") is True
        line_status = "EXACT LINE MATCH" if same_line else "LIVE LINE MOVED"
        status_class = "match" if same_line else "moved"
        rows.append(
            '<div class="ks157-row">'
            f'<span>#{rank} {team}</span><span>MLB {context["official_game_id"]}</span>'
            f'<strong>{_line(context["live_fanduel_line"])} • {_odds(context["live_fanduel_odds"])}</strong>'
            f'<em class="{status_class}">{line_status}</em>'
            '</div>'
        )

    collected = escape(str(state.get("collected_at_utc") or "timestamp unavailable"))
    age = state.get("snapshot_age_seconds")
    age_text = "age unavailable" if age is None else f"{float(age):.1f}s old"
    status = escape(str(state.get("integration_status") or FALLBACK).replace("_", " "))
    return (
        '<style>'
        '.ks157-board{margin:8px 0 10px;border:1px solid #31506a;background:#07121d;border-radius:12px;padding:9px}'
        '.ks157-head{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:.52rem;font-weight:950;color:#9bd6ff;margin-bottom:6px}'
        '.ks157-row{display:grid;grid-template-columns:1.3fr .65fr .9fr .9fr;gap:7px;align-items:center;padding:6px 5px;border-top:1px solid rgba(80,125,155,.2);font-size:.48rem;color:#b9ccd9}'
        '.ks157-row strong{color:#f5fbff}.ks157-row em{font-style:normal;font-weight:900;color:#8da5b5}.ks157-row em.match{color:#79e5ae}.ks157-row em.moved{color:#ffd479}'
        '.ks157-foot{font-size:.42rem;color:#71899a;line-height:1.45;margin-top:6px}'
        '@media(max-width:640px){.ks157-row{grid-template-columns:1.2fr .7fr 1fr}.ks157-row em{grid-column:1/-1}}'
        '</style>'
        '<div class="ks157-board">'
        '<div class="ks157-head"><span>STEP 7B • LIVE FANDUEL RUN LINE • EXACT MLB GAME ID</span>'
        f'<span>{status}</span></div>'
        + "".join(rows)
        + f'<div class="ks157-foot">Snapshot {collected} • {escape(age_text)} • display-only API context. '
        'A live line move is shown, never substituted into the frozen V15.6 model. '
        'Snapshots older than 60 seconds fail back to the frozen presentation. '
        'No API evidence changes projection, probability, simulation, H2H adjustment, ranking, selection, or fair odds.</div></div>'
    )


def _render_api_market_strip(results, status_info, team_logo, h, *, state):
    st.markdown(_market_strip_html(list(results or []), state, h), unsafe_allow_html=True)


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    """Render V15.6.4 unchanged, with an additive API Run Line strip."""
    state = _cached_spread_api_state(_api_base_url())
    st.session_state[_STATE_KEY] = dict(state)

    frozen_cards = prior.base._render_cards

    def cards_with_api_context(results, status_info_inner, team_logo_inner, h_inner):
        _render_api_market_strip(
            results,
            status_info_inner,
            team_logo_inner,
            h_inner,
            state=state,
        )
        return frozen_cards(results, status_info_inner, team_logo_inner, h_inner)

    prior.base._render_cards = cards_with_api_context
    try:
        if state.get("integration_status") == API_CONNECTED and state.get("feed_fresh") is True:
            st.caption(
                "🔗 MLB Spread Step 7B • fresh Kyre Sports API exact-ID FanDuel Run Line context is active above the existing Top-5 cards • model math unchanged."
            )
        else:
            st.caption(
                "⚪ MLB Spread Step 7B • API market context is unavailable or stale, so the frozen V15.6.4 Spread presentation remains authoritative and unchanged."
            )
        return prior.render_spread_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior.base._render_cards = frozen_cards


__all__ = [
    "DEFAULT_API_BASE_URL",
    "MODEL_VERSION",
    "render_spread_hub",
]
