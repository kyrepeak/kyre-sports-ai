"""Server-side Page 1 client for Kyre Sports API NBA player context."""
from __future__ import annotations

from datetime import date
import os
from typing import Any, Callable, Mapping, Sequence

import requests

DEFAULT_API_BASE_URL = "https://kyre-runless-proof.vercel.app"


def _empty(state: str, names: Sequence[str]) -> dict[str, Any]:
    return {
        "source": "Kyre Sports API — Vercel",
        "verification": "DATA_UNAVAILABLE",
        "diagnostic_state": state,
        "profiles": {},
        "provider_health": {},
        "requested_players": len(names),
        "verified_players": 0,
        "fabrication": False,
    }


def load_kyre_sports_api_player_context(
    slate_date: date,
    player_names: Sequence[str],
    *,
    request_post: Callable[..., Any] | None = None,
    base_url: str | None = None,
    timeout: tuple[float, float] = (3.0, 24.0),
) -> dict[str, Any]:
    """Load player identity/history only through the Kyre Sports API gateway."""
    names = [" ".join(str(name or "").split()) for name in player_names]
    names = [name for name in names if name]
    if not names:
        return _empty("NO_PLAYERS", names)
    request_post = request_post or requests.post
    base_url = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    try:
        response = request_post(
            f"{base_url}/api/v1/nba/pra/player-context",
            json={"date": slate_date.isoformat(), "player_names": names},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _empty(f"KYRE_VERCEL_ERROR:{type(exc).__name__}", names)
    if not isinstance(payload, Mapping) or payload.get("fabrication") is not False:
        return _empty("KYRE_VERCEL_CONTRACT_INVALID", names)
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping):
        return _empty("KYRE_VERCEL_PROFILES_INVALID", names)
    return {
        "source": "Kyre Sports API — Vercel",
        "verification": str(payload.get("verification") or "DATA_UNAVAILABLE"),
        "diagnostic_state": "OK" if profiles else "NO_VERIFIED_PLAYER_CONTEXT",
        "profiles": {str(k): dict(v) for k, v in profiles.items() if isinstance(v, Mapping)},
        "provider_health": dict(payload.get("provider_health") or {}),
        "requested_players": int(payload.get("requested_players") or len(names)),
        "verified_players": int(payload.get("verified_players") or 0),
        "fabrication": False,
    }
