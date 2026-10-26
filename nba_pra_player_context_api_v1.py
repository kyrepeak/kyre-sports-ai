"""Server-side Page 1 client for Kyre Sports API NBA player context."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date
import os
import time
from typing import Any, Callable, Mapping, Sequence

import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
PLAYER_CONTEXT_CACHE_TTL_SECONDS = 300.0
HISTORY_BATCH_SIZE = 16
HISTORY_MAX_WORKERS = 4
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


def _fetch_payload(
    *,
    request_post: Callable[..., Any],
    url: str,
    slate_date: date,
    names: Sequence[str],
    codes: Sequence[str],
    timeout: tuple[float, float],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = request_post(
            url,
            json={"date": slate_date.isoformat(), "player_names": list(names), "team_codes": list(codes)},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return None, f"KYRE_VERCEL_ERROR:{type(exc).__name__}"
    if not isinstance(payload, Mapping) or payload.get("fabrication") is not False:
        return None, "KYRE_VERCEL_CONTRACT_INVALID"
    if not isinstance(payload.get("profiles"), Mapping):
        return None, "KYRE_VERCEL_PROFILES_INVALID"
    return dict(payload), None


def _merge_history_batches(payloads: Sequence[Mapping[str, Any]], names: Sequence[str]) -> dict[str, Any]:
    profiles: dict[str, dict[str, Any]] = {}
    provider_health: dict[str, Any] = {}
    verified = 0
    identified = 0
    for payload in payloads:
        for key, row in (payload.get("profiles") or {}).items():
            if isinstance(row, Mapping):
                profiles[str(key)] = dict(row)
        for key, value in (payload.get("provider_health") or {}).items():
            provider_health[str(key)] = deepcopy(value)
        verified += int(payload.get("verified_players") or 0)
        identified += int(payload.get("identified_players") or payload.get("verified_players") or 0)
    requested = len(names)
    verification = "VERIFIED" if requested and verified >= requested else "PARTIAL" if identified else "DATA_UNAVAILABLE"
    return {
        "source": "Kyre Sports API — Vercel",
        "verification": verification,
        "diagnostic_state": "OK" if profiles else "NO_VERIFIED_PLAYER_CONTEXT",
        "profiles": profiles,
        "provider_health": provider_health,
        "requested_players": requested,
        "verified_players": min(verified, requested),
        "identified_players": min(identified, requested),
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
    """Load verified player context only through Kyre Sports API.

    Page 1 history-only requests are split into bounded concurrent batches so a
    full sportsbook slate stays inside the client deadline. Full-context Page 2
    requests remain single-player/single-request and keep usage enrichment.
    """
    names = [" ".join(str(name or "").split()) for name in player_names]
    names = [name for name in names if name]
    if not names:
        return _empty("NO_PLAYERS", names)
    codes: list[str] = []
    seen_codes: set[str] = set()
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

    route = "/api/v1/nba/pra/player-context" if include_usage else "/api/v1/nba/pra/player-context/history"
    url = f"{base_url}{route}"
    if include_usage or len(names) <= HISTORY_BATCH_SIZE:
        payload, error = _fetch_payload(
            request_post=request_post,
            url=url,
            slate_date=slate_date,
            names=names,
            codes=codes,
            timeout=timeout,
        )
        if error is not None or payload is None:
            return _empty(error or "KYRE_VERCEL_CONTEXT_UNAVAILABLE", names)
        result = _merge_history_batches([payload], names)
    else:
        chunks = [names[index:index + HISTORY_BATCH_SIZE] for index in range(0, len(names), HISTORY_BATCH_SIZE)]
        payloads: list[dict[str, Any]] = []
        error_state: str | None = None
        with ThreadPoolExecutor(max_workers=min(HISTORY_MAX_WORKERS, len(chunks))) as pool:
            futures = [
                pool.submit(
                    _fetch_payload,
                    request_post=request_post,
                    url=url,
                    slate_date=slate_date,
                    names=chunk,
                    codes=codes,
                    timeout=timeout,
                )
                for chunk in chunks
            ]
            for future in as_completed(futures):
                payload, error = future.result()
                if error is not None or payload is None:
                    error_state = error or "KYRE_VERCEL_CONTEXT_UNAVAILABLE"
                    break
                payloads.append(payload)
            if error_state is not None:
                for future in futures:
                    future.cancel()
                return _empty(error_state, names)
        result = _merge_history_batches(payloads, names)

    _cache_put(cache_key, result)
    return deepcopy(result)
