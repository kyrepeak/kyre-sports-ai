"""API-only NBA PRA Page 1 routing overlay.

The live Page 1 calls Kyre Sports API for market observations and player
enrichment. Provider-specific network traffic never originates from Streamlit.
Legacy provider parameters remain compatibility-only and are never executed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import requests

import nba_pra_page1_data_core_v2 as _core
import nba_pra_page1_data_v2 as _legacy
from nba_pra_enrichment_api_v1 import load_kyre_sports_api_nba_enrichment
from nba_pra_market_api_v1 import load_kyre_sports_api_pra_observations


def _filter_payload_to_games(payload: Mapping[str, Any], games) -> dict[str, Any]:
    return _legacy._filter_payload_to_games(payload, games)


def _api_only_secondary() -> dict[str, Any]:
    return {
        "source": "Kyre Sports API — API-only Page 1",
        "verification": "SKIPPED_API_ONLY",
        "diagnostic_state": "SKIPPED_API_ONLY",
        "observations": [],
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
    }


def load_page1_snapshot_v2(
    *,
    now=None,
    schedule_loader=None,
    api_loader=None,
    enrichment_loader=None,
    sgo_loader=None,
    odds_loader=None,
    official_profile_loader=None,
    backup_profile_loader=None,
    injury_loader=None,
    schedule_recovery_get=None,
):
    """Build Page 1 with Kyre Sports API as the page-facing data authority."""
    # Compatibility-only inputs. The live Page 1 path never executes them.
    del sgo_loader, odds_loader
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    schedule_impl = schedule_loader or _core._default_schedule_loader
    api_impl = api_loader or load_kyre_sports_api_pra_observations
    enrichment_impl = enrichment_loader or load_kyre_sports_api_nba_enrichment
    state: dict[str, Any] = {}

    def schedule_proxy(**kwargs):
        result = dict(schedule_impl(**kwargs) or {})
        result = _legacy._recover_quorum_schedule(
            result,
            now_utc,
            request_get=schedule_recovery_get or requests.get,
        )
        _, games = _core.select_next_upcoming_slate(list(result.get("games") or []), now_utc)
        state["games"] = games
        return result

    def primary_proxy(day):
        api_result = _filter_payload_to_games(dict(api_impl(day) or {}), state.get("games", []))
        state["api"] = api_result
        names = list(dict.fromkeys(
            str(row.get("player_name") or "").strip()
            for row in api_result.get("observations", [])
            if isinstance(row, Mapping) and str(row.get("player_name") or "").strip()
        ))
        state["enrichment"] = dict(enrichment_impl(day, names) or {}) if names else {
            "data_state": "DATA_UNAVAILABLE",
            "profiles": {},
            "provider_health": {},
            "requested_players": 0,
            "verified_players": 0,
            "fabrication": False,
        }
        return api_result

    def secondary_proxy(_day):
        return _api_only_secondary()

    def enriched_profile_proxy(_day):
        return dict((state.get("enrichment") or {}).get("profiles") or {})

    def no_legacy_profile_rescue(_names, _day):
        return {}

    result = _core.load_page1_snapshot_v2(
        now=now_utc,
        schedule_loader=schedule_proxy,
        sgo_loader=primary_proxy,
        odds_loader=secondary_proxy,
        official_profile_loader=official_profile_loader or enriched_profile_proxy,
        backup_profile_loader=backup_profile_loader or no_legacy_profile_rescue,
        injury_loader=injury_loader,
    )
    sources = dict(result.get("sources") or {})
    sources["kyre_sports_api"] = state.get("api") or {
        "source": "Kyre Sports API — Vercel",
        "verification": "UNAVAILABLE",
        "diagnostic_state": "NO_API_RESULT",
        "observations": [],
    }
    enrichment = state.get("enrichment") or {}
    sources["nba_enrichment"] = {
        "source": "Kyre Sports API — NBA Data Router",
        "verification": str(enrichment.get("data_state") or "DATA_UNAVAILABLE"),
        "diagnostic_state": "OK" if enrichment.get("verified_players") else "DATA_UNAVAILABLE",
        "provider_health": dict(enrichment.get("provider_health") or {}),
        "requested_players": int(enrichment.get("requested_players") or 0),
        "verified_players": int(enrichment.get("verified_players") or 0),
        "fabrication": False,
    }
    result["sources"] = sources
    return result
