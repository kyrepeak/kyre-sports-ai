"""Server-side Page 1 client for Kyre Sports API NBA player context."""
from __future__ import annotations

from datetime import date
from copy import deepcopy
import os
import time
from typing import Any, Callable, Mapping, Sequence

import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
PLAYER_CONTEXT_CACHE_TTL_SECONDS = 300.0
_PLAYER_CONTEXT_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}


def _clear_player_context_cache() -> None:
    _PLAYER_CONTEXT_CACHE.clear()


def _cache_get(key: tuple[Any, ...], ttl_seconds: float) -> dict[str, Any] | None:
    cached = _PLAYER_CONTEXT_CACHE.get(key)
    if cached is None:
        return None
    stored_at, payload = cached
    if time.monotonic() - stored_at > ttl_seconds:
        _PLAYER_CONTEXT_CACHE.pop(key, None)
        return None
    return deepcopy(payload)


def _cache_put(key: tuple[Any, ...], payload: Mapping[str, Any]) -> None:
    if len(_PLAYER_CONTEXT_CACHE) >= 16:
        oldest = min(_PLAYER_CONTEXT_CACHE, key=lambda item: _PLAYER_CONTEXT_CACHE[item][0])
        _PLAYER_CONTEXT_CACHE.pop(oldest, None)
    _PLAYER_CONTEXT_CACHE[key] = (time.monotonic(), deepcopy(dict(payload)))


def _empty(state: str, names: Sequence[str]) -> dict[str, Any]:
    return {
        "source": "Kyre Sports API — Vercel",
        "verification": "DATA_UNAVAILABLE",
        "diagnostic_state": state,
        "profiles": {},
        "provider_health": {},
        "requested_players": len(names),
        "verified_players": 0,
        "identified_players": 0,
        "fabrication": False,
    }


def load_kyre_sports_api_player_context(
    slate_date: date,
    player_names: Sequence[str],
    *,
    team_codes: Sequence[str] | None = None,
    include_usage: bool = False,
    request_post: Callable[..., Any] | None = None,
    base_url: str | None = None,
    timeout: tuple[float, float] = (3.0, 24.0),
) -> dict[str, Any]:
    """Load player identity/history only through the Kyre Sports API gateway."""
    names = [" ".join(str(name or "").split()) for name in player_names]
    names = [name for name in names if name]
    if not names:
        return _empty("NO_PLAYERS", names)
    codes = []
    seen_codes = set()
    for raw_code in team_codes or []:
        code = " ".join(str(raw_code or "").split()).upper()
        if code and code not in seen_codes:
            codes.append(code)
            seen_codes.add(code)
    request_post = request_post or requests.post
    base_url = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    cache_key = (slate_date.isoformat(), tuple(names), tuple(codes), bool(include_usage), base_url, id(request_post))
    cached = _cache_get(cache_key, PLAYER_CONTEXT_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        route = "/api/v1/nba/pra/player-context" if include_usage else "/api/v1/nba/pra/player-context/history"
        response = request_post(
            f"{base_url}{route}",
            json={"date": slate_date.isoformat(), "player_names": names, "team_codes": codes},
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
    result = {
        "source": "Kyre Sports API — Vercel",
        "verification": str(payload.get("verification") or "DATA_UNAVAILABLE"),
        "diagnostic_state": "OK" if profiles else "NO_VERIFIED_PLAYER_CONTEXT",
        "profiles": {str(k): dict(v) for k, v in profiles.items() if isinstance(v, Mapping)},
        "provider_health": dict(payload.get("provider_health") or {}),
        "requested_players": int(payload.get("requested_players") or len(names)),
        "verified_players": int(payload.get("verified_players") or 0),
        "identified_players": int(payload.get("identified_players") or payload.get("verified_players") or 0),
        "fabrication": False,
    }
    _cache_put(cache_key, result)
    return deepcopy(result)
