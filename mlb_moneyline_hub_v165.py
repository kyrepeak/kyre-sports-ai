"""MLB Moneyline V16.5 — clean mobile presentation over frozen V16.3+ model chain.

V16.5 preserves the existing V16.3/V16.2/V16.1/V16 Moneyline schedule,
projection, simulation, probability, H2H adjustment, ranking, selection and fair
odds. It also preserves Step 7C's read-only exact-ID FanDuel API context.

Presentation-only changes:
- restore scoped card CSS under the memory-safe Streamlit router;
- collapse the existing live sportsbook board behind a closed expander;
- replace repetitive implementation captions with one concise frozen-model note;
- keep H2H/recent-form detail collapsed until requested.
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

MODEL_VERSION = "V16.5 • CLEAN MOBILE PRESENTATION • FROZEN MONEYLINE MODEL"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
_STATE_KEY = "mlb_step7c_moneyline_api_integration_v1"
FROZEN_MODEL_CHAIN = (
    "mlb_moneyline_hub_v163",
    "moneyline_hub_v162",
    "moneyline_hub_v161",
    "moneyline_hub_v16",
)

_TECHNICAL_CAPTION_MARKERS = (
    "Moneyline V16.3 isolation",
    "V16.2 adds a live sportsbook market layer",
)

_CSS = r"""
<style>
.ks-pick-card{
  display:grid;grid-template-columns:minmax(0,1fr) auto;
  grid-template-areas:"rank rank" "main right";gap:10px 14px;
  margin:12px 0;padding:14px;border:1px solid rgba(118,171,211,.28);
  border-radius:18px;background:linear-gradient(145deg,rgba(12,26,45,.98),rgba(7,17,31,.98));
  box-shadow:0 8px 24px rgba(0,0,0,.18);overflow:hidden;
}
.ks-pick-card.ks-first{border-color:rgba(255,207,84,.55);box-shadow:0 9px 28px rgba(0,0,0,.22),0 0 0 1px rgba(255,207,84,.08) inset}
.ks-rank{grid-area:rank;font-size:.86rem;font-weight:900;letter-spacing:.02em;color:#f3f7fb}
.ks-card-main{grid-area:main;min-width:0}.ks-player-row{display:flex;align-items:center;gap:11px;min-width:0}
.ks-player-row img{width:48px!important;height:48px!important;max-width:48px!important;object-fit:contain;flex:0 0 48px}
.ks-player-copy{min-width:0}.ks-player{font-size:1.06rem;line-height:1.15;font-weight:900;color:#f8fbff;margin-bottom:4px}
.ks-matchup{color:#a9bac9;font-size:.76rem;line-height:1.45}
.ks-meta-line{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:10px}
.ks-mini,.ks-status,.ks-badge{display:inline-flex;align-items:center;min-height:27px;padding:4px 8px;border-radius:999px;font-size:.68rem;font-weight:800;line-height:1;white-space:nowrap}
.ks-mini{background:rgba(121,151,176,.11);border:1px solid rgba(121,151,176,.17);color:#c7d4df}
.ks-status{background:rgba(101,199,151,.12);border:1px solid rgba(101,199,151,.24);color:#9ae4bd}
.ks-badge{border:1px solid rgba(121,151,176,.22)}.ks-high{background:rgba(72,199,142,.13);color:#8de0b5}.ks-medium{background:rgba(242,189,83,.12);color:#f2cf85}.ks-low{background:rgba(239,111,111,.12);color:#efaaaa}
.ks-card-details{margin-top:10px;border-top:1px solid rgba(121,151,176,.14);padding-top:8px}
.ks-card-details summary{cursor:pointer;color:#9cb2c4;font-size:.72rem;font-weight:800;list-style:none}.ks-card-details summary::-webkit-details-marker{display:none}
.ks-detail-body{padding:9px 0 2px;color:#aebdca;font-size:.70rem;line-height:1.58}.ks-detail-body b{color:#edf5fb}
.ks-right{grid-area:right;align-self:center;min-width:108px;text-align:right;padding-left:12px;border-left:1px solid rgba(121,151,176,.14)}
.ks-prob{font-size:1.75rem;line-height:1;font-weight:950;letter-spacing:-.04em;color:#f9fcff}.ks-prob-label{margin-top:4px;color:#8fa4b5;font-size:.64rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
.ks-card-meta{display:flex;flex-direction:column;align-items:flex-end;gap:6px;margin-top:10px}.ks-card-meta .ks-mini{background:transparent;border-color:rgba(121,151,176,.20)}
.ks164-board{margin:10px 0 12px!important;border-radius:14px!important}.ks164-head{font-size:.68rem!important}.ks164-row{font-size:.64rem!important}.ks164-foot{font-size:.58rem!important}
@media(max-width:640px){
  .ks-pick-card{padding:12px;gap:10px 9px;grid-template-columns:minmax(0,1fr) 92px}.ks-player-row{align-items:flex-start}
  .ks-player-row img{width:42px!important;height:42px!important;max-width:42px!important;flex-basis:42px}.ks-player{font-size:.98rem}.ks-matchup{font-size:.70rem}
  .ks-right{min-width:0;padding-left:8px}.ks-prob{font-size:1.52rem}.ks-mini,.ks-status,.ks-badge{font-size:.61rem;min-height:25px;padding:4px 7px}
  .ks164-row{grid-template-columns:1.15fr .85fr 1fr!important}.ks164-row em{grid-column:1/-1}
}
</style>
"""


def _api_base_url() -> str:
    value = os.getenv("KYRE_SPORTS_API_BASE_URL") or os.getenv("SPORTS_API_BASE_URL") or DEFAULT_API_BASE_URL
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
            headers={"Accept": "application/json", "User-Agent": "KyreSportsMLBMoneylineStep7C/1.0", "Cache-Control": "no-cache"},
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
                f'<em>Model fair {fair} • frozen card unchanged</em></div>'
            )
        else:
            rows.append(
                '<div class="ks164-row">'
                f'<span>#{rank} {team}</span><span>MLB {context["official_game_id"]}</span>'
                f'<strong>FanDuel {_odds(context["live_fanduel_odds"])}</strong>'
                f'<em>Model fair {fair} • display only</em></div>'
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
        '</style><div class="ks164-board">'
        '<div class="ks164-head"><span>LIVE FANDUEL MONEYLINE • EXACT MLB GAME ID</span>'
        f'<span>{status}</span></div>' + "".join(rows)
        + f'<div class="ks164-foot">Snapshot {collected} • {escape(age_text)} • display-only market context. Model math remains frozen.</div></div>'
    )


def _render_api_market_strip(results, status_info, team_logo, h, *, state):
    st.markdown(_market_strip_html(list(results or []), state), unsafe_allow_html=True)


def _compact_live_board(original):
    def wrapped(games_df, *args: Any, **kwargs: Any):
        with st.expander("📡 Live sportsbook board", expanded=False):
            return original(games_df, *args, **kwargs)
    return wrapped


def _filtered_caption(original):
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        if any(marker in str(body or "") for marker in _TECHNICAL_CAPTION_MARKERS):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def _render_frozen_chain(games_df, section_header, status_info, team_logo, h, state):
    if state.get("integration_status") != API_CONNECTED:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)

    v161 = prior.base.base
    frozen_cards = v161._render_cards_v161

    def cards_with_api_context(results, status_info_inner, team_logo_inner, h_inner):
        _render_api_market_strip(results, status_info_inner, team_logo_inner, h_inner, state=state)
        return frozen_cards(results, status_info_inner, team_logo_inner, h_inner)

    v161._render_cards_v161 = cards_with_api_context
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        v161._render_cards_v161 = frozen_cards


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render frozen Moneyline behavior with V16.5 mobile/readability styling."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.caption("🔒 Moneyline frozen • model probabilities, simulation, H2H adjustment, ranking and fair odds unchanged • FanDuel context is display-only.")

    state = _cached_moneyline_api_state(_api_base_url())
    st.session_state[_STATE_KEY] = dict(state)

    v162 = prior.base
    original_live_board = v162.render_live_slate_board
    original_caption = st.caption
    v162.render_live_slate_board = _compact_live_board(original_live_board)
    st.caption = _filtered_caption(original_caption)
    try:
        return _render_frozen_chain(games_df, section_header, status_info, team_logo, h, state)
    finally:
        st.caption = original_caption
        v162.render_live_slate_board = original_live_board


__all__ = ["DEFAULT_API_BASE_URL", "FROZEN_MODEL_CHAIN", "MODEL_VERSION", "render_moneyline_hub"]
