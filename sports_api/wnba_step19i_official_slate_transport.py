"""WNBA Step 19I: official slate transport compatibility.

Step19H proved that the hosted FanDuel responses are valid JSON and isolated the
remaining generic Step11C JSON failure to its separate official WNBA schedule
CDN request.  Step7G already contains a certified first-party WNBA.com schedule
adapter that was created specifically to bypass cloud-network failures on the
CDN/stats schedule surfaces.

This compatibility layer reuses that existing official WNBA.com first-party raw
schedule payload only for Step11C's internal official-schedule GET.  FanDuel
transport, frozen event/player reconciliation, Step10 validation, controller
state, readiness gates, projections, persistence, and wagering behavior remain
unchanged.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19h_fanduel_hosted_transport as step19h
from sports_api import wnba_step7g_first_party_schedule as first_party_schedule
from sports_api.wnba_official_reconciliation import parse_official_schedule
from sports_api.wnba_schedule import WNBAScheduleUpstreamError, _schedule_root

SOURCE = "Kyre Sports API WNBA Step19I official slate transport compatibility"
MODEL_VERSION = "wnba_step19i_official_slate_transport_v1"
CERTIFIED_SEASON = 2026

_ORIGINAL_GET_JSON = fanduel._get_json
_FIRST_PARTY_SCHEDULE_LOADER = first_party_schedule._fetch_first_party_schedule_payload
_INSTALLED = False


def _load_certified_first_party_schedule() -> dict[str, Any]:
    """Load and revalidate the exact raw official WNBA.com season document."""
    try:
        payload, _retrieved_at, source_variant, source_url, _cache_hit = (
            _FIRST_PARTY_SCHEDULE_LOADER(CERTIFIED_SEASON)
        )
    except WNBAScheduleUpstreamError as exc:
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA first-party schedule transport failed."
        ) from exc

    if not isinstance(payload, dict):
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA first-party schedule returned non-object JSON."
        )
    try:
        root = _schedule_root(payload)
    except WNBAScheduleUpstreamError as exc:
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA first-party schedule failed schema validation."
        ) from exc
    if str(root.get("seasonYear")) != str(CERTIFIED_SEASON):
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA first-party schedule season identity mismatch."
        )
    if not parse_official_schedule(payload):
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA first-party schedule contained no reconcilable games."
        )
    if source_variant != first_party_schedule.FIRST_PARTY_SOURCE_VARIANT:
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA schedule source variant was not first-party."
        )
    if not str(source_url or "").startswith(first_party_schedule.FIRST_PARTY_SCHEDULE_URL):
        raise fanduel.WNBAStep11FanDuelProviderUpstreamError(
            "Step 19I official WNBA schedule source URL was not the certified first-party route."
        )
    return deepcopy(payload)


def fanduel_get_json_step19i(
    url: str,
    *,
    params: Mapping[str, Any] | None,
    requester: Callable[..., Any] | None,
    timeout: float,
) -> dict[str, Any]:
    """Route only Step11C's duplicate official schedule read to Step7G first-party."""
    if url != fanduel.OFFICIAL_SCHEDULE_URL:
        return _ORIGINAL_GET_JSON(
            url,
            params=params,
            requester=requester,
            timeout=timeout,
        )

    # Preserve explicit caller-controlled requesters used by frozen unit tests
    # and offline evidence fixtures.  Step19H's hosted diagnostic requester is
    # the production default-transport wrapper and is intentionally bypassed
    # for this one official schedule read.
    if requester is not None and requester is not step19h.diagnostic_requester:
        return _ORIGINAL_GET_JSON(
            url,
            params=params,
            requester=requester,
            timeout=timeout,
        )

    return _load_certified_first_party_schedule()


def install_step19i_official_slate_transport() -> dict[str, Any]:
    """Install Step19H diagnostics plus the one-route official slate repair."""
    global _INSTALLED
    step19h.install_step19h_fanduel_hosted_transport()
    if fanduel._get_json is not fanduel_get_json_step19i:
        fanduel._get_json = fanduel_get_json_step19i
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    return {
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "installed": _INSTALLED,
        "official_schedule_transport_active": fanduel._get_json is fanduel_get_json_step19i,
        "official_source_variant": first_party_schedule.FIRST_PARTY_SOURCE_VARIANT,
        "official_source_url": first_party_schedule.FIRST_PARTY_SCHEDULE_URL,
        "sportsbook_transport_modified": False,
        "official_identity_parser_modified": False,
        "game_uniqueness_relaxed": False,
        "player_identity_relaxed": False,
        "readiness_relaxed": False,
        "provider_retry_policy_modified": False,
        "projection_logic_modified": False,
        "controller_state_modified": False,
        "persistence_modified": False,
        "wagering_enabled": False,
    }


__all__ = [
    "CERTIFIED_SEASON",
    "MODEL_VERSION",
    "SOURCE",
    "fanduel_get_json_step19i",
    "install_step19i_official_slate_transport",
    "installation_status",
]
