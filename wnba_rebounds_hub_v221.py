"""WNBA Rebounds V2.2.1 — Step 13 subscription-safe SportsGameOdds fetch.

Preserves V2.2 Step-13 market parsing and exact same-book/same-line pairing,
but fixes provider connection for API tiers that do not permit every requested
bookmakerID. SportsGameOdds documents bookmakerID as optional and may filter
restricted bookmaker odds from a successful response with a notice. Therefore
this build does NOT explicitly request inaccessible bookmaker IDs; it requests
the WNBA events once and locally keeps only the target sportsbook IDs already
supported by V2.2.

No sportsbook line is fabricated. No consensus odds, no-vig, EV, Monte Carlo,
or final rebound projection is introduced here.
"""
from __future__ import annotations

import requests
import streamlit as st

import wnba_rebounds_hub_v22 as base

MODEL_VERSION = "WNBA REBOUNDS V2.2.1 • STEP 13 SUBSCRIPTION-SAFE SPORTSGAMEODDS"


@st.cache_data(ttl=90, show_spinner=False, max_entries=8)
def _fetch_sgo_events_tier_safe(api_key: str):
    """Fetch WNBA events without forcing bookmaker IDs unavailable to this tier.

    SportsGameOdds v2 allows bookmakerID to be omitted. When a subscription has
    restricted bookmaker access, the provider can return a successful response
    with accessible bookmaker data filtered to the plan instead of rejecting the
    entire request because one named bookmaker is unavailable.
    """
    if not api_key:
        return [], {
            "ok": False,
            "status_code": 0,
            "error": "SportsGameOdds API key is not connected.",
            "request_mode": "subscription-safe",
        }

    try:
        response = requests.get(
            f"{base.SGO_API_BASE}/events",
            params={
                "leagueID": "WNBA",
                "oddsAvailable": "true",
                "finalized": "false",
                "limit": 100,
                # IMPORTANT: bookmakerID intentionally omitted. Requesting even
                # one bookmaker outside the account tier can reject the entire
                # query. V2.2 still filters returned byBookmaker rows locally to
                # base.SGO_BOOKMAKERS and keeps each book separate.
                "includeAltLines": "false",
            },
            headers={"x-api-key": api_key},
            timeout=12,
        )
    except Exception as exc:
        return [], {
            "ok": False,
            "status_code": 0,
            "error": f"SportsGameOdds request failed: {type(exc).__name__}",
            "request_mode": "subscription-safe",
        }

    status = int(response.status_code)
    try:
        payload = response.json()
    except Exception:
        payload = {}

    if status != 200:
        provider_error = ""
        if isinstance(payload, dict):
            provider_error = str(payload.get("error") or payload.get("message") or "")
        return [], {
            "ok": False,
            "status_code": status,
            "error": provider_error or f"SportsGameOdds HTTP {status}",
            "request_mode": "subscription-safe",
        }

    data = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(data, list):
        data = []
    success = bool(payload.get("success", True)) if isinstance(payload, dict) else False
    notice = str(payload.get("notice") or "") if isinstance(payload, dict) else ""

    return data, {
        "ok": bool(success),
        "status_code": status,
        "error": "" if success else str(payload.get("error") or "Provider returned success=false"),
        "events": int(len(data)),
        "notice": notice,
        "request_mode": "subscription-safe • bookmakerID omitted • local target-book filter",
    }


def render_wnba_rebounds_hub(*args, **kwargs):
    # Patch only the provider fetch for this render. All V2.2 parsing, event
    # reconciliation, player identity rules and same-book/same-line O/U pairing
    # remain unchanged.
    old_fetch = base._fetch_sgo_events
    base._fetch_sgo_events = _fetch_sgo_events_tier_safe
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
        st.caption(
            "⚡ V2.2.1 Step-13 provider repair • subscription-safe SportsGameOdds request • "
            "bookmakerID filter omitted at provider request • accessible books filtered locally • "
            "no fabricated lines / consensus / no-vig / EV / Monte Carlo / final projection."
        )
        return out
    finally:
        base._fetch_sgo_events = old_fetch


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
