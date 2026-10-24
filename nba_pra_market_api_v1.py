"""Server-side Streamlit client for the Kyre Sports API NBA PRA transport."""
from __future__ import annotations

from datetime import date
import os
from typing import Any, Callable, Mapping

import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
APPROVED_BOOKS = {"FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics Sportsbook"}


def _empty(state: str) -> dict[str, Any]:
    return {
        "source": "Kyre Sports API — Vercel",
        "ready": False,
        "verification": "UNAVAILABLE",
        "diagnostic_state": state,
        "observations": [],
        "provider_health": [],
        "provider_route_audit": [],
        "recent_participant_profiles": {},
        "recent_participant_state": "UNAVAILABLE",
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
    }


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (value or []) if isinstance(row, Mapping)]


def _profile_map(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): dict(row)
        for key, row in value.items()
        if isinstance(row, Mapping)
    }


def load_kyre_sports_api_pra_observations(
    slate_date: date,
    *,
    api_key: str | None = None,
    request_post: Callable[..., Any] | None = None,
    base_url: str | None = None,
    timeout: tuple[float, float] = (3.0, 22.0),
) -> dict[str, Any]:
    """Load NBA PRA only through Kyre Sports API.

    ``api_key`` remains only for compatibility with older callers. It is ignored
    and never transmitted. Provider routing, fallbacks, provider-local health,
    and semantic global market state remain server-side Kyre Sports API duties.
    """
    del api_key
    request_post = request_post or requests.post
    base_url = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    try:
        response = request_post(
            f"{base_url}/api/v1/nba/pra/market",
            json={"date": slate_date.isoformat()},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _empty(f"KYRE_VERCEL_ERROR:{type(exc).__name__}")
    if (
        not isinstance(payload, Mapping)
        or payload.get("projection_weight") != 0.0
        or payload.get("consensus_averaging") is not False
    ):
        return _empty("KYRE_VERCEL_CONTRACT_INVALID")

    rows: list[dict[str, Any]] = []
    for raw in payload.get("observations") or []:
        if not isinstance(raw, Mapping):
            continue
        book = str(raw.get("sportsbook") or "").strip()
        side = str(raw.get("side") or "").strip().casefold()
        try:
            line = float(raw.get("line"))
        except (TypeError, ValueError):
            continue
        if book not in APPROVED_BOOKS or side not in {"over", "under"}:
            continue
        row = dict(raw)
        row["line"] = line
        rows.append(row)

    return {
        "source": "Kyre Sports API — Vercel",
        "ready": bool(rows),
        "verification": "VERIFIED" if rows else "UNAVAILABLE",
        "diagnostic_state": "OK" if rows else str(payload.get("diagnostic_state") or "KYRE_VERCEL_NO_PRA"),
        "global_market_state_reason": str(payload.get("global_market_state_reason") or ""),
        "player_count": int(payload.get("player_count") or 0),
        "observation_count": len(rows),
        "observations": rows,
        "provider_health": _mapping_rows(payload.get("provider_health")),
        "provider_route_audit": _mapping_rows(payload.get("provider_route_audit")),
        "recent_participant_profiles": _profile_map(payload.get("recent_participant_profiles")),
        "recent_participant_state": str(payload.get("recent_participant_state") or ""),
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
    }
