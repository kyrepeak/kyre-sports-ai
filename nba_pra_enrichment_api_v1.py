"""Streamlit-side NBA enrichment client. Provider calls remain behind Kyre Sports API."""
from __future__ import annotations

from datetime import date
import os
from typing import Any, Callable, Mapping, Sequence

import requests

DEFAULT_API_BASE_URL = "https://kyre-runless-proof.vercel.app"


def _empty(state: str, player_names: Sequence[str]) -> dict[str, Any]:
    return {
        "schema_version": "KYRE_NBA_ENRICHMENT_V1",
        "data_state": "DATA_UNAVAILABLE",
        "profiles": {},
        "provider_health": {},
        "requested_players": len(player_names),
        "verified_players": 0,
        "diagnostic_state": state,
        "fabrication": False,
    }


def load_kyre_sports_api_nba_enrichment(
    slate_date: date,
    player_names: Sequence[str],
    *,
    request_post: Callable[..., Any] | None = None,
    base_url: str | None = None,
    timeout: tuple[float, float] = (3.0, 90.0),
) -> dict[str, Any]:
    """Load player enrichment only from Kyre Sports API."""
    names = [" ".join(str(name or "").split()) for name in player_names]
    names = list(dict.fromkeys(name for name in names if name))
    if not names:
        return _empty("NO_PLAYERS", names)
    request_post = request_post or requests.post
    base_url = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    try:
        response = request_post(
            f"{base_url}/api/v1/nba/pra/market/enrichment",
            json={"date": slate_date.isoformat(), "player_names": names},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _empty(f"KYRE_ENRICHMENT_ERROR:{type(exc).__name__}", names)
    if not isinstance(payload, Mapping) or payload.get("fabrication") is not False:
        return _empty("KYRE_ENRICHMENT_CONTRACT_INVALID", names)
    profiles = payload.get("profiles")
    health = payload.get("provider_health")
    if not isinstance(profiles, Mapping) or not isinstance(health, Mapping):
        return _empty("KYRE_ENRICHMENT_CONTRACT_INVALID", names)
    return dict(payload)
