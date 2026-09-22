"""MLB Totals V17.4 — Step 7E exact-ID FanDuel Game Total presentation.

This wrapper keeps the existing V17.3/V17.2/V17.1 Totals chain authoritative
and adds one read-only Kyre Sports API market strip immediately above the
existing Top-5 O/U cards. FanDuel Total line and Over/Under prices are display
context only: they never replace the frozen settlement line, projection,
simulation, probability, ranking, selection, history adjustment, or fair odds.

If transport, contract, exact-ID identity, required prices, or freshness cannot
be proven, V17.3 renders normally with no synthetic market evidence.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import requests
import streamlit as st

import mlb_totals_hub_v173 as prior
from sports_api.mlb_step7d_total_api_integration_v1 import (
    API_CONNECTED,
    FALLBACK,
    build_total_api_state,
    enforce_total_api_freshness,
    total_api_context_for_result,
)

MODEL_VERSION = "V17.4 • STEP 7E • EXACT-ID FANDUEL GAME TOTAL API CONTEXT"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
_STATE_KEY = "mlb_step7e_game_total_presentation_integration_v1"


def _api_base_url() -> str:
    value = (
        os.getenv("KYRE_SPORTS_API_BASE_URL")
        or os.getenv("SPORTS_API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )
    return str(value).strip().rstrip("/")


@st.cache_data(ttl=30, show_spinner=False)
def _cached_total_api_state(base_url: str) -> dict[str, Any]:
    root = str(base_url or "").strip().rstrip("/")
    if not root:
        return {
            "data_type": "mlb_step7d_total_api_integration_v1",
            "schema_version": 1,
            "integration_status": FALLBACK,
            "api_integration_active": False,
            "source": "FanDuel",
            "match_method": "official_mlb_game_id_exact",
            "fallback_matching_used": False,
            "feed_fresh": False,
            "failures": ["api_base_url_empty"],
        }
    try:
        response = requests.get(
            f"{root}/api/v1/mlb/odds",
            params={"max_events": 30, "fully_priced_only": "true"},
            timeout=25,
            headers={
                "Accept": "application/json",
                "User-Agent": "KyreSportsMLBTotalsStep7E/1.0",
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        state = enforce_total_api_freshness(build_total_api_state(response.json()))
        state["http_status"] = int(response.status_code)
        return state
    except Exception as exc:
        return {
            "data_type": "mlb_step7d_total_api_integration_v1",
            "schema_version": 1,
            "integration_status": FALLBACK,
            "api_integration_active": False,
            "source": "FanDuel",
            "match_method": "official_mlb_game_id_exact",
            "fallback_matching_used": False,
            "feed_fresh": False,
            "preexisting_presentation_preserved": True,
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


def _line(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except Exception:
        return "—"


def _market_strip_html(results: list[Mapping[str, Any]], state: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for rank, result in enumerate(list(results or [])[:5], 1):
        context = total_api_context_for_result(result, state)
        game = escape(
            f'{str(result.get("away_team") or "Away")} @ {str(result.get("home_team") or "Home")}'
        )
        game_id = escape(str(result.get("game_pk") or "—"))
        model_line = result.get("total_line")
        if context is None:
            rows.append(
                '<div class="ks174-row">'
                f'<span>#{rank} {game}</span><span>MLB {game_id}</span>'
                '<strong>API CONTEXT UNAVAILABLE</strong>'
                '<em>Frozen V17.3/V17.2/V17.1 output unchanged</em>'
                '</div>'
            )
            continue

        live_line = context.get("live_fanduel_total_line")
        try:
            exact_line = abs(float(model_line) - float(live_line)) <= 1e-9
        except Exception:
            exact_line = False
        line_status = "EXACT LINE MATCH" if exact_line else "LIVE LINE DIFFERS"
        status_class = "match" if exact_line else "moved"
        rows.append(
            '<div class="ks174-row">'
            f'<span>#{rank} {game}</span><span>MLB {context["official_game_id"]}</span>'
            f'<strong>O/U {_line(live_line)} • O {_odds(context["live_fanduel_over_odds"])} • U {_odds(context["live_fanduel_under_odds"])}</strong>'
            f'<em class="{status_class}">{line_status} • model line {_line(model_line)}</em>'
            '</div>'
        )

    collected = escape(str(state.get("collected_at_utc") or "timestamp unavailable"))
    age = state.get("snapshot_age_seconds")
    age_text = f"{float(age):.1f}s old" if isinstance(age, (int, float)) else "age unavailable"
    status = escape(str(state.get("integration_status") or FALLBACK).replace("_", " "))
    return (
        '<style>'
        '.ks174-board{margin:8px 0 10px;border:1px solid #31506a;background:#07121d;border-radius:12px;padding:9px}'
        '.ks174-head{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:.52rem;font-weight:950;color:#9bd6ff;margin-bottom:6px}'
        '.ks174-row{display:grid;grid-template-columns:1.35fr .55fr 1.25fr 1.25fr;gap:7px;align-items:center;padding:6px 5px;border-top:1px solid rgba(80,125,155,.2);font-size:.48rem;color:#b9ccd9}'
        '.ks174-row strong{color:#f5fbff}.ks174-row em{font-style:normal;font-weight:900;color:#8da5b5}.ks174-row em.match{color:#79e5ae}.ks174-row em.moved{color:#ffd479}'
        '.ks174-foot{font-size:.42rem;color:#71899a;line-height:1.45;margin-top:6px}'
        '@media(max-width:640px){.ks174-row{grid-template-columns:1.2fr .7fr 1.25fr}.ks174-row em{grid-column:1/-1}}'
        '</style>'
        '<div class="ks174-board">'
        '<div class="ks174-head"><span>STEP 7E • LIVE FANDUEL GAME TOTAL • EXACT MLB GAME ID</span>'
        f'<span>{status}</span></div>'
        + "".join(rows)
        + f'<div class="ks174-foot">Snapshot {collected} • {escape(age_text)} • display-only API context. '
        'The FanDuel Total line and prices are never substituted into the frozen V17.3/V17.2/V17.1 model or settlement-line path. '
        'No API evidence changes projection, simulation, O/U probability, history adjustment, ranking, selection, or fair odds.</div></div>'
    )


def _render_api_market_strip(results, status_info, team_logo, h, *, state):
    st.markdown(_market_strip_html(list(results or []), state), unsafe_allow_html=True)


def render_totals_hub(games_df, section_header, status_info, team_logo, h):
    """Render V17.3 unchanged, adding only a fresh exact-ID FanDuel Total strip."""
    state = _cached_total_api_state(_api_base_url())
    st.session_state[_STATE_KEY] = dict(state)

    v171 = prior.base.base
    frozen_cards = v171._render_ou_cards

    def cards_with_api_context(results, status_info_inner, team_logo_inner, h_inner):
        _render_api_market_strip(
            results,
            status_info_inner,
            team_logo_inner,
            h_inner,
            state=state,
        )
        return frozen_cards(results, status_info_inner, team_logo_inner, h_inner)

    v171._render_ou_cards = cards_with_api_context
    try:
        if state.get("integration_status") == API_CONNECTED and state.get("feed_fresh") is True:
            st.caption(
                "🔗 MLB Totals Step 7E • fresh Kyre Sports API exact-ID FanDuel Game Total context is active above the existing O/U cards • model math unchanged."
            )
        else:
            st.caption(
                "⚪ MLB Totals Step 7E • API Game Total context is unavailable or stale, so the frozen V17.3 presentation remains authoritative and unchanged."
            )
        return prior.render_totals_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        v171._render_ou_cards = frozen_cards


__all__ = [
    "DEFAULT_API_BASE_URL",
    "MODEL_VERSION",
    "render_totals_hub",
]
