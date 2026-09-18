"""CFB Game Total Clean Page V15 — V164 universal exact team logos.

Additive presentation-only successor to permanently frozen V163/V14. V164 keeps
all V163 selector, model, market, qualification and ranking behavior unchanged,
and enriches only missing display-logo team IDs from official ESPN event
identity before the frozen exact-ID logo resolver runs.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v14 as prior_v163
import cfb_game_total_team_logo_identity_v1 as logo_identity
import cfb_game_total_runtime_display_v1 as runtime_display
import cfb_over_under_logo_resolver_v3 as frozen_logo

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V15 • V164 UNIVERSAL EXACT TEAM LOGOS"
MARKET = prior_v163.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v14"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V164 ACTIVE"
LOGO_POLICY = "official ESPN event_id -> exact ESPN team IDs -> ESPN NCAA logo CDN"

_FROZEN_RESOLVE_VISUALS = frozen_logo.resolve_visuals
_FROZEN_RECONCILE_DISPLAY_BUNDLE = runtime_display.reconcile_display_bundle


def _selector_payload_for_day(selected_day: Any) -> dict[str, Any]:
    requested_day = selected_day.isoformat() if isinstance(selected_day, date) else str(selected_day or "")[:10]
    if not requested_day:
        return {}
    try:
        return prior_v163._fetch_selector_identity_payload(date.fromisoformat(requested_day))
    except (TypeError, ValueError):
        return {}


def _selector_payload_for_game(game: Mapping[str, Any]) -> dict[str, Any]:
    return _selector_payload_for_day(logo_identity._game_date(game))


def _reconcile_display_bundle_v164(
    game: Mapping[str, Any],
    selected_day: Any,
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
):
    """Enrich only the display copy with exact ESPN team IDs before logo resolution."""
    display_game, away, home, diag = _FROZEN_RECONCILE_DISPLAY_BUNDLE(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    enriched = dict(display_game or game)
    event_id = logo_identity._event_id(game) or logo_identity._event_id(enriched)
    if event_id and not logo_identity._event_id(enriched):
        enriched["espn_event_id"] = event_id

    payload = _selector_payload_for_day(selected_day)
    enriched = logo_identity.enrich_exact_team_ids(enriched, payload)

    out_diag = dict(diag or {})
    away_id = str(enriched.get("away_espn_team_id") or "").strip()
    home_id = str(enriched.get("home_espn_team_id") or "").strip()
    out_diag["v164_logo_team_ids_enriched"] = bool(away_id.isdigit() and home_id.isdigit())
    out_diag["v164_logo_identity_source"] = str(enriched.get("logo_identity_source") or "")
    return enriched, away, home, out_diag


def _resolve_visuals_v164(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return logo_identity.resolve_visuals(
        game,
        _FROZEN_RESOLVE_VISUALS,
        _selector_payload_for_game(game),
    )


def _render_v164_identity() -> None:
    st.markdown(
        '<div data-testid="cfb-game-total-v164-active" '
        'style="display:none!important">'
        f'{ACTIVE_MARKER} • exact ESPN team logos • V163 frozen parent • '
        'sportsbook projection influence 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    original_resolver = frozen_logo.resolve_visuals
    original_reconcile = runtime_display.reconcile_display_bundle
    frozen_logo.resolve_visuals = _resolve_visuals_v164
    runtime_display.reconcile_display_bundle = _reconcile_display_bundle_v164
    try:
        result = prior_v163.render_game_total_hub(section_header, status_info, team_logo, h)
        _render_v164_identity()
        return result
    finally:
        runtime_display.reconcile_display_bundle = original_reconcile
        frozen_logo.resolve_visuals = original_resolver


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V164 Game Total V15 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "LOGO_POLICY",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_reconcile_display_bundle_v164",
    "_resolve_visuals_v164",
    "_selector_payload_for_day",
    "_selector_payload_for_game",
    "render_cfb_hub",
    "render_game_total_hub",
]
