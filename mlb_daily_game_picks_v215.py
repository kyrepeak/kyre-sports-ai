"""MLB Daily Game Picks V2.1.5 — multi-provider sportsbook bridge.

Transport/orchestration upgrade only. Preserves V2.1.4b 429 quarantine,
V2.1.3 persistent completed-card snapshots, all seven existing production model
formulas and simulation depths, Step 3 normalization, Step 5/6 rankings, live
risk checks, team logos and identity firewalls.

Sportsbook routing for the existing Run Line + Total production connectors:
1. SportsGameOdds is PRIMARY when SPORTSGAMEODDS_API_KEY is configured.
2. Odds-API.io remains FALLBACK using its proven V2.0.5 cooldown logic.
3. Both providers feed the exact same normalized snapshot contract.
4. Run Line and Total still share one cached slate snapshot and never fabricate
   a sportsbook line.
"""
from __future__ import annotations

import time

import requests
import streamlit as st

import mlb_daily_game_picks_v204 as market_bridge
import mlb_daily_game_picks_v205 as quota
import mlb_daily_game_picks_v214b as previous
import sportsbook_multi_provider_v1 as multi_odds

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.5 • MULTI-PROVIDER SPORTSBOOK"
CACHE_TTL_SECONDS = 180

# Capture the proven Odds-API.io V2.0.5 fetch before this wrapper patches the
# module global. This preserves its existing Retry-After/429 cooldown behavior.
_LEGACY_GET_ODDS = quota._get_odds


def _provider_stamp_key(day):
    return f"dgp_multi_provider_v215_stamp::{day}"


def _provider_name_key(day):
    return f"dgp_multi_provider_v215_name::{day}"


def _activation_key(day):
    return f"dgp_multi_provider_v215_activation::{day}"


def _redacted_error(exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status:
        return f"HTTP {status}"
    return type(exc).__name__


def _multi_get_odds(games_df, force=False):
    """Shared Run Line/Total fetch: SGO first, legacy provider second."""
    day = market_bridge._day(games_df)
    state_key = market_bridge._odds_key(day)
    stamp_key = _provider_stamp_key(day)

    cached = st.session_state.get(state_key)
    stamp = st.session_state.get(stamp_key)
    if cached:
        try:
            fresh = stamp is None or (time.time() - float(stamp)) <= CACHE_TTL_SECONDS
        except Exception:
            fresh = True
        if fresh:
            return cached, ""

    primary_key = multi_odds.get_sgo_api_key()
    primary_error = None

    if primary_key:
        try:
            snaps = multi_odds.sportsgameodds_snapshots(games_df) or {}
            if snaps:
                st.session_state[state_key] = snaps
                st.session_state[stamp_key] = time.time()
                st.session_state[_provider_name_key(day)] = "SportsGameOdds"
                # A legacy Odds-API.io cooldown must never block a successful new
                # primary-provider slate snapshot.
                st.session_state.pop(quota._cooldown_key(day), None)
                return snaps, ""
            primary_error = "SportsGameOdds returned no matched MLB markets for this slate."
        except requests.HTTPError as exc:
            primary_error = f"SportsGameOdds {_redacted_error(exc)}"
        except Exception as exc:
            primary_error = f"SportsGameOdds {type(exc).__name__}"

    legacy_key = market_bridge._clean_key(multi_odds.get_legacy_api_key())
    if legacy_key:
        # Delegate fallback to the untouched V2.0.5 function so its existing
        # shared cache and provider-reset cooldown semantics remain intact.
        snaps, legacy_error = _LEGACY_GET_ODDS(games_df, force=force)
        if snaps:
            st.session_state[state_key] = snaps
            st.session_state[stamp_key] = time.time()
            st.session_state[_provider_name_key(day)] = "Odds-API.io fallback"
            return snaps, ""
        if legacy_error:
            prefix = f"{primary_error} • " if primary_error else ""
            return {}, prefix + str(legacy_error)

    if primary_error:
        return {}, (
            f"{primary_error} No usable fallback sportsbook snapshot is available. "
            "No sportsbook line was fabricated."
        )

    return {}, (
        "Sportsbook odds are not connected. Add SPORTSGAMEODDS_API_KEY in Streamlit Secrets; "
        "ODDS_API_IO_KEY can remain configured as fallback. No sportsbook line was fabricated."
    )


def _activate_primary_without_legacy_wait(games_df):
    """Let a newly configured SGO key bypass an OLD legacy 429 exactly once."""
    day = market_bridge._day(games_df)
    if not day or not multi_odds.get_sgo_api_key():
        return
    activation = _activation_key(day)
    if st.session_state.get(activation):
        return
    st.session_state[activation] = True
    st.session_state.pop(quota._cooldown_key(day), None)


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # V2.0.5 re-installs its own _get_odds into V2.0.4 on every inherited render.
    # Patch BOTH module globals so the new routing survives Streamlit reruns.
    quota._get_odds = _multi_get_odds
    market_bridge._get_odds = _multi_get_odds
    _activate_primary_without_legacy_wait(games_df)

    day = market_bridge._day(games_df)
    provider = st.session_state.get(_provider_name_key(day)) or (
        "SportsGameOdds primary" if multi_odds.get_sgo_api_key()
        else "Odds-API.io fallback" if multi_odds.get_legacy_api_key()
        else "waiting for API key"
    )
    st.caption(
        f"🔄 V2.1.5 multi-provider sportsbook bridge: {provider} • Run Line + Total share one normalized slate cache • production model math unchanged."
    )

    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
