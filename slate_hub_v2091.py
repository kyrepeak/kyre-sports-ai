"""V20.9.2 sportsbook provider bridge + V20.9.1 recursion hotfix.

Preserves every V20.9 freshness, no-vig, stale-filtering, matchup, lineup and
independent model feature while routing the MLB Slate sportsbook snapshot through
one normalized multi-provider layer:

1. SportsGameOdds is primary when SPORTSGAMEODDS_API_KEY is configured.
2. Odds-API.io remains the automatic fallback.
3. Both providers are converted to the exact same normalized snapshot contract
   before V20.9 model-vs-market logic sees them.
4. No projection, Monte Carlo, no-vig, ranking or grading math is changed.

Also preserves the V20.9.1 no-market recursion fix.
"""
from __future__ import annotations

import requests
import streamlit as st

import slate_hub_v205 as base205
import slate_hub_v208 as base208
import slate_hub_v209 as base209
import sportsbook_multi_provider_v1 as multi_odds

MODEL_VERSION = "V20.9.2"

_ORIGINAL_EDGE_V209 = base209._edge_card_v209


def _edge_card_v2091(title, item):
    if not item:
        return (
            '<div class="sl-edge pass"><div class="sl-edge-top">'
            f'<span class="sl-edge-market">{base209.escape(title)}</span>'
            '<span class="sl-edge-grade">NO MARKET</span></div>'
            '<div class="sl-edge-pick">Waiting for matching line</div>'
            '<div class="sl-edge-detail">A calibrated comparison appears when the model and a compatible two-way sportsbook market are both available.</div>'
            '</div>'
        )
    return _ORIGINAL_EDGE_V209(title, item)


def _safe_snapshots_multi(games_df, api_key=None, bookmakers=None):
    """Return the existing V20 normalized snapshot contract from either provider."""
    try:
        return multi_odds.snapshots_for_games_multi(games_df, fallback=True)
    except requests.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            raise RuntimeError(
                "Sportsbook provider rejected a saved API key. Check SPORTSGAMEODDS_API_KEY first; Odds-API.io remains the fallback."
            ) from None
        if status == 429:
            raise RuntimeError(
                "Available sportsbook providers are temporarily rate-limited. Cached markets remain untouched; retry after the provider reset."
            ) from None
        raise RuntimeError(
            f"Sportsbook provider is temporarily unavailable (HTTP {status or 'error'})."
        ) from None
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError(
            "Sportsbook feed could not refresh right now. No API key or market line was exposed or fabricated."
        ) from None


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    old_edge = base209._edge_card_v209
    old_version = base209.MODEL_VERSION
    old_safe = base205._safe_snapshots
    old_raw_key = base208._raw_get_api_key
    old_books = base208.get_bookmakers

    # V20.8 resolves these names at render time, so patching them here changes
    # only sportsbook transport—not the model or UI math layered above it.
    base209._edge_card_v209 = _edge_card_v2091
    base209.MODEL_VERSION = MODEL_VERSION
    base205._safe_snapshots = _safe_snapshots_multi
    base208._raw_get_api_key = lambda: (
        multi_odds.get_sgo_api_key() or multi_odds.get_legacy_api_key()
    )
    base208.get_bookmakers = multi_odds.get_display_bookmakers

    try:
        if multi_odds.get_sgo_api_key():
            st.caption(
                "🔄 V20.9.2 sportsbook routing: SportsGameOdds PRIMARY • Odds-API.io FALLBACK • one normalized MLB market contract • existing model math unchanged."
            )
        elif multi_odds.get_legacy_api_key():
            st.caption(
                "🔄 V20.9.2 sportsbook routing: Odds-API.io active as fallback-only until SPORTSGAMEODDS_API_KEY is added to Streamlit Secrets."
            )
        else:
            st.caption(
                "🔑 V20.9.2 sportsbook routing is ready. Add SPORTSGAMEODDS_API_KEY to Streamlit Secrets to activate SportsGameOdds."
            )
        return base209.render_slate_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        base209._edge_card_v209 = old_edge
        base209.MODEL_VERSION = old_version
        base205._safe_snapshots = old_safe
        base208._raw_get_api_key = old_raw_key
        base208.get_bookmakers = old_books
