"""MLB Step 8F — exact-ID FanDuel player-prop presentation integration.

This module is a presentation-only bridge over the certified Step 8A/8C/8D/8E
contracts. It fetches the existing read-only ``/api/v1/mlb/player-props`` payload,
proves freshness through Step 8A, then decorates the already-produced Pitcher K,
1+ Hit, and H+R+RBI cards only when the exact official MLB game ID + player ID +
market identity is available.

Sportsbook context is never a model input. Projection, simulation, probability,
line grading, qualification, confidence, ranking, selection, fair odds, history,
calibration, persistence, and wagering behavior remain owned by the frozen model
stacks. Missing, stale, ambiguous, mismatched, or tampered API context fails open
to the pre-existing card HTML without synthetic evidence.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape
import os
from typing import Any, Mapping

import requests
import streamlit as st

from sports_api.mlb_step8a_player_prop_api_contract_v1 import (
    API_CONNECTED,
    HITS_RUNS_RBI,
    PITCHER_STRIKEOUTS,
    PLAYER_HITS,
    build_player_prop_api_state,
    enforce_player_prop_api_freshness,
)
from sports_api.mlb_step8c_pitcher_strikeouts_integration_v1 import (
    ATTACHMENT_KEY as PITCHER_ATTACHMENT_KEY,
    build_pitcher_strikeout_integration,
    enrich_pitcher_strikeout_results,
)
from sports_api.mlb_step8d_player_hits_integration_v1 import (
    ATTACHMENT_KEY as HITS_ATTACHMENT_KEY,
    build_player_hits_integration,
    enrich_player_hit_results,
)
from sports_api.mlb_step8e_hits_runs_rbi_integration_v1 import (
    ATTACHMENT_KEY as HRRBI_ATTACHMENT_KEY,
    build_hits_runs_rbi_integration,
    enrich_hits_runs_rbi_results,
)

DATA_TYPE = "mlb_step8f_player_prop_presentation_integration_v1"
SCHEMA_VERSION = 1
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
STATE_KEY = "mlb_step8f_player_prop_presentation_integration_v1"

_MARKET_LABELS = {
    PITCHER_STRIKEOUTS: "Pitcher Strikeouts",
    PLAYER_HITS: "Player Hits",
    HITS_RUNS_RBI: "Hits + Runs + RBI",
}
_CURRENT_STATE_BY_MARKET: dict[str, dict[str, Any]] = {}

_CSS = r"""
<style>
.ks8f-prop-context{
    margin:8px 0 4px;padding:8px 9px;border:1px solid #31556d;
    background:linear-gradient(145deg,#081924,#07131c);border-radius:10px;
    font-size:.50rem;line-height:1.42;color:#a9c2d1;
}
.ks8f-prop-context .ks8f-kicker{
    color:#69d8ff;font-size:.43rem;font-weight:1000;letter-spacing:.08em;
    text-transform:uppercase;margin-bottom:3px;
}
.ks8f-prop-context strong{color:#f5fbff;font-size:.56rem}
.ks8f-prop-context em{display:block;color:#7892a4;font-style:normal;margin-top:3px}
.ks8f-prop-context .ks8f-exact{color:#79e6b0;font-weight:950}
</style>
"""


def _fallback_state(reason: str) -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_status": "PLAYER_PROP_API_CONTEXT_UNAVAILABLE",
        "api_integration_active": False,
        "source": "FanDuel",
        "match_method": "official_mlb_game_id_player_id_market_exact",
        "fallback_matching_used": False,
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
        "feed_fresh": False,
        "sportsbook_price_model_input": False,
        "model_math_impact": False,
        "projection_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "line_grading_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "production_exposure_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
        "failures": [str(reason)],
    }


def _api_base_url() -> str:
    value = (
        os.getenv("KYRE_SPORTS_API_BASE_URL")
        or os.getenv("SPORTS_API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )
    return str(value).strip().rstrip("/")


def build_step8f_player_prop_api_state(
    payload: Mapping[str, Any] | None,
    *,
    as_of_utc: Any = None,
    max_age_seconds: float = 60.0,
) -> dict[str, Any]:
    """Build the certified Step 8A state used by presentation wrappers."""
    raw = build_player_prop_api_state(payload)
    return enforce_player_prop_api_freshness(
        raw,
        as_of_utc=as_of_utc,
        max_age_seconds=max_age_seconds,
    )


@st.cache_data(ttl=30, show_spinner=False)
def _cached_player_prop_api_state(base_url: str) -> dict[str, Any]:
    root = str(base_url or "").strip().rstrip("/")
    if not root:
        return _fallback_state("api_base_url_empty")
    try:
        response = requests.get(
            f"{root}/api/v1/mlb/player-props",
            params={"max_events": 30},
            timeout=25,
            headers={
                "Accept": "application/json",
                "User-Agent": "KyreSportsMLBPlayerPropsStep8F/1.0",
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        state = build_step8f_player_prop_api_state(response.json())
        state["http_status"] = int(response.status_code)
        return state
    except Exception as exc:
        return _fallback_state(f"transport_or_contract_error:{type(exc).__name__}")


def _context_for_result(
    result: Mapping[str, Any] | None,
    market_type: str,
    api_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return one certified display attachment without mutating the result."""
    if not isinstance(result, Mapping):
        return None
    before = deepcopy(dict(result))
    row = deepcopy(dict(result))

    if market_type == PITCHER_STRIKEOUTS:
        integration = build_pitcher_strikeout_integration([row], api_state)
        enriched = enrich_pitcher_strikeout_results([row], integration)
        key = PITCHER_ATTACHMENT_KEY
    elif market_type == PLAYER_HITS:
        integration = build_player_hits_integration([row], api_state)
        enriched = enrich_player_hit_results([row], integration)
        key = HITS_ATTACHMENT_KEY
    elif market_type == HITS_RUNS_RBI:
        integration = build_hits_runs_rbi_integration([row], api_state)
        enriched = enrich_hits_runs_rbi_results([row], integration)
        key = HRRBI_ATTACHMENT_KEY
    else:
        return None

    if dict(result) != before or not enriched:
        return None
    context = enriched[0].get(key) if isinstance(enriched[0], Mapping) else None
    if not isinstance(context, Mapping):
        return None
    context = dict(context)
    if (
        context.get("market_type") != market_type
        or context.get("display_only") is not True
        or context.get("feed_fresh") is not True
        or context.get("fallback_matching_used") is not False
        or context.get("player_name_matching_used") is not False
        or context.get("sportsbook_price_model_input") is not False
    ):
        return None
    return context


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


def _context_strip_html(context: Mapping[str, Any], market_type: str) -> str:
    label = escape(_MARKET_LABELS.get(market_type, str(market_type)))
    line = escape(_line(context.get("line")))
    over = escape(_odds(context.get("over_odds")))
    under = escape(_odds(context.get("under_odds")))
    game_id = escape(str(context.get("official_game_id") or "—"))
    return (
        '<div class="ks8f-prop-context">'
        f'<div class="ks8f-kicker">STEP 8F • FANDUEL {label} • EXACT MLB ID</div>'
        f'<strong>O/U {line} • Over {over} • Under {under}</strong>'
        f'<em><span class="ks8f-exact">EXACT ID MATCH</span> • MLB game {game_id} • display only • frozen model unchanged</em>'
        '</div>'
    )


def decorate_card_html(
    html: Any,
    result: Mapping[str, Any] | None,
    market_type: str,
    api_state: Mapping[str, Any] | None,
) -> str:
    """Add one display strip; return prior HTML byte-for-byte when unavailable."""
    original = html if isinstance(html, str) else str(html or "")
    context = _context_for_result(result, market_type, api_state)
    if context is None:
        return original
    strip = _context_strip_html(context, market_type)
    marker = "</div>"
    split_at = original.rfind(marker)
    if split_at < 0:
        return original + strip
    return original[:split_at] + strip + original[split_at:]


def _state_caption(market_type: str, state: Mapping[str, Any]) -> None:
    label = _MARKET_LABELS.get(market_type, market_type)
    if state.get("integration_status") == API_CONNECTED and state.get("feed_fresh") is True:
        st.caption(
            f"🔗 MLB Step 8F • fresh exact-ID FanDuel {label} context is enabled on matching cards • model math and ranking unchanged."
        )
    else:
        st.caption(
            f"⚪ MLB Step 8F • certified FanDuel {label} context is unavailable or stale • existing presentation remains authoritative and unchanged."
        )


def _wrap_renderer(module: Any, attr: str, market_type: str) -> None:
    current = getattr(module, attr)
    original = getattr(current, "_step8f_original_renderer", current)

    def wrapped(*args, **kwargs):
        state = _cached_player_prop_api_state(_api_base_url())
        _CURRENT_STATE_BY_MARKET[market_type] = dict(state)
        try:
            st.markdown(_CSS, unsafe_allow_html=True)
            _state_caption(market_type, state)
            st.session_state[STATE_KEY] = {
                "data_type": DATA_TYPE,
                "schema_version": SCHEMA_VERSION,
                "market_type": market_type,
                "integration_status": state.get("integration_status"),
                "api_integration_active": state.get("api_integration_active") is True,
                "feed_fresh": state.get("feed_fresh") is True,
                "match_method": state.get("match_method"),
                "player_name_matching_used": False,
                "sportsbook_price_model_input": False,
                "model_math_impact": False,
                "ranking_impact": False,
                "failures": list(state.get("failures") or []),
            }
            return original(*args, **kwargs)
        finally:
            _CURRENT_STATE_BY_MARKET.pop(market_type, None)

    wrapped._step8f_original_renderer = original
    setattr(module, attr, wrapped)


def _wrap_pitcher_card(module: Any) -> None:
    current = getattr(module, "_card_with_headshot")
    original = getattr(current, "_step8f_original_card", current)

    def wrapped(result, rank):
        html = original(result, rank)
        return decorate_card_html(
            html,
            result,
            PITCHER_STRIKEOUTS,
            _CURRENT_STATE_BY_MARKET.get(PITCHER_STRIKEOUTS),
        )

    wrapped._step8f_original_card = original
    module._card_with_headshot = wrapped


def _wrap_hit_card(module: Any) -> None:
    current = getattr(module.active, "_pick_html")
    original = getattr(current, "_step8f_original_card", current)

    def wrapped(result, rank):
        html = original(result, rank)
        return decorate_card_html(
            html,
            result,
            PLAYER_HITS,
            _CURRENT_STATE_BY_MARKET.get(PLAYER_HITS),
        )

    wrapped._step8f_original_card = original
    module.active._pick_html = wrapped


def _wrap_hrrbi_card(module: Any) -> None:
    current = getattr(module.base, "_card")
    original = getattr(current, "_step8f_original_card", current)

    def wrapped(result, rank, threshold):
        html = original(result, rank, threshold)
        return decorate_card_html(
            html,
            result,
            HITS_RUNS_RBI,
            _CURRENT_STATE_BY_MARKET.get(HITS_RUNS_RBI),
        )

    wrapped._step8f_original_card = original
    module.base._card = wrapped


def install_step8f_player_prop_presentation() -> dict[str, Any]:
    """Patch only the three already-loaded player-prop presentation boundaries."""
    import mlb_pitcher_k_hub_v1017 as pitcher
    import mlb_hit_hub_v1315 as hits
    import mlb_hrrbi_hub_v115 as hrrbi

    required = (
        hasattr(pitcher, "_card_with_headshot") and hasattr(pitcher, "render_pitcher_k_hub"),
        hasattr(hits, "active") and hasattr(hits, "render_hit_hub"),
        hasattr(hrrbi, "base") and hasattr(hrrbi, "render_hrrbi_hub"),
    )
    if not all(required):
        raise RuntimeError("Step 8F frozen player-prop presentation boundaries are unavailable.")

    _wrap_pitcher_card(pitcher)
    _wrap_hit_card(hits)
    _wrap_hrrbi_card(hrrbi)
    _wrap_renderer(pitcher, "render_pitcher_k_hub", PITCHER_STRIKEOUTS)
    _wrap_renderer(hits, "render_hit_hub", PLAYER_HITS)
    _wrap_renderer(hrrbi, "render_hrrbi_hub", HITS_RUNS_RBI)

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "installed": True,
        "markets": [PITCHER_STRIKEOUTS, PLAYER_HITS, HITS_RUNS_RBI],
        "match_method": "official_mlb_game_id_player_id_market_exact",
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
        "sportsbook_price_model_input": False,
        "model_math_impact": False,
        "projection_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "line_grading_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }


__all__ = [
    "DATA_TYPE",
    "DEFAULT_API_BASE_URL",
    "SCHEMA_VERSION",
    "STATE_KEY",
    "build_step8f_player_prop_api_state",
    "decorate_card_html",
    "install_step8f_player_prop_presentation",
]
