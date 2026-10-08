"""CFB Game Total clean page V38 — Step 4 runtime ownership repair.

Additive successor to the frozen Step-4 V37 presentation. V38 preserves the
approved Prediction + Market Comparison helper, but hardens runtime ownership by
covering both the V9 base analysis seam and the V26 presentation seam during the
render call. It also reuses the existing identity-verified Kyre Sports API /
FanDuel total-market contract before the existing exact-event side-market
context is applied. Market data remains context-only with 0.0% projection
weight and fails closed when exact identity verification is unavailable.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v9 as base_analysis_owner
import cfb_game_total_clean_page_v26 as v26_analysis_owner
import cfb_game_total_clean_page_v36 as prior
import cfb_game_total_clean_page_v37 as frozen_step4
import cfb_game_total_page1_step4_prediction_market_v1 as prediction
import cfb_game_total_page1_step4_side_market_v1 as side_market
import cfb_over_under_market_adapter_v1 as market_adapter

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V38 • PAGE1 V2 STEP4 RUNTIME REPAIR"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v37"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE1 V2 STEP4 RUNTIME REPAIR ACTIVE"
STEP4_MARKER = prediction.STEP4_MARKER
STEP4_CSS = frozen_step4.STEP4_CSS

_LOCK = RLock()
_MARKET_KEYS = (
    "market_line_available",
    "market_identity_verified",
    "market_reason",
    "market_official_game_id",
    "market_provider_game_id",
    "market_total",
    "market_sportsbook",
    "market_status",
    "market_updated_at_utc",
    "market_captured_at_utc",
    "market_source",
    "market_projection_weight",
    "market_context_only",
    "market_may_modify_projection",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _event_id(display_game: Mapping[str, Any]) -> str:
    for key in ("espn_event_id", "event_id", "game_id", "id"):
        value = _clean(display_game.get(key))
        if value:
            return value
    return ""


def _game_date(display_game: Mapping[str, Any]) -> str:
    for key in ("game_date", "date", "start_date"):
        value = _clean(display_game.get(key))
        if value:
            return value[:10]
    return ""


def _enrich_verified_total_market(display_game: Mapping[str, Any]) -> dict[str, Any]:
    """Prefer the existing identity-verified FanDuel total feed; otherwise preserve input."""
    out = dict(display_game or {})
    event_id = _event_id(out)
    game_date = _game_date(out)
    if not event_id or not game_date:
        return out

    try:
        payload, diagnostics = market_adapter.load_odds_for_date(game_date, "FanDuel")
        probe = dict(out)
        probe["espn_event_id"] = event_id
        attached, attach_diagnostics = market_adapter.attach_market_lines([probe], payload)
    except Exception:
        return out

    if not attached:
        return out
    row = attached[0]
    if row.get("market_line_available") is not True:
        return out
    if row.get("market_identity_verified") is not True:
        return out
    try:
        projection_weight = float(row.get("market_projection_weight"))
    except (TypeError, ValueError):
        return out
    if projection_weight != 0.0:
        return out

    for key in _MARKET_KEYS:
        if key in row:
            out[key] = row[key]
    out["verified_total_market_provider"] = _clean(row.get("market_sportsbook")) or "FanDuel"
    out["verified_total_market_source"] = _clean(row.get("market_source"))
    out["verified_total_market_event_id"] = event_id
    out["verified_total_market_projection_weight"] = 0.0
    if isinstance(diagnostics, Mapping):
        out["verified_total_market_diagnostics"] = {
            "status": diagnostics.get("status"),
            "sportsbook": diagnostics.get("sportsbook"),
            "projection_weight": diagnostics.get("projection_weight", 0.0),
        }
    if isinstance(attach_diagnostics, Mapping):
        out["verified_total_market_attach"] = {
            "market_lines_attached": attach_diagnostics.get("market_lines_attached"),
            "matching_method": attach_diagnostics.get("matching_method"),
            "projection_weight": attach_diagnostics.get("projection_weight", 0.0),
        }
    return out


def _step4_prediction_market_html_v38(
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    display_game: Mapping[str, Any],
    statuses: Mapping[int, str],
    ready_count: int,
) -> str:
    total_enriched = _enrich_verified_total_market(display_game)
    fully_enriched = side_market.enrich_verified_side_market(total_enriched)
    return prediction.build_prediction_market_html(
        raw,
        final,
        fully_enriched,
        statuses,
        ready_count,
    )


def _render_with_step4_runtime_owner(callback, *args, **kwargs):
    """Cover both known analysis ownership paths for the duration of one render."""
    with _LOCK:
        original_base = base_analysis_owner._game_total_hero_html
        original_v26 = v26_analysis_owner._game_total_analysis_html_v26
        base_analysis_owner._game_total_hero_html = _step4_prediction_market_html_v38
        v26_analysis_owner._game_total_analysis_html_v26 = _step4_prediction_market_html_v38
        try:
            return callback(*args, **kwargs)
        finally:
            base_analysis_owner._game_total_hero_html = original_base
            v26_analysis_owner._game_total_analysis_html_v26 = original_v26


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP4_CSS, unsafe_allow_html=True)
    result = _render_with_step4_runtime_owner(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP4_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page V38 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_CSS",
    "STEP4_MARKER",
    "_enrich_verified_total_market",
    "_render_with_step4_runtime_owner",
    "_step4_prediction_market_html_v38",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
