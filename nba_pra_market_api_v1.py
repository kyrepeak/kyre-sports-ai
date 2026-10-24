"""Server-side Streamlit client for the Kyre Sports API NBA PRA transport."""
from __future__ import annotations

from datetime import date
import os
from typing import Any, Callable, Mapping

import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
APPROVED_BOOKS = {"FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics Sportsbook"}


def _default_the_odds_api_key() -> str | None:
    """Read only official The Odds API credentials from server-side config."""
    for name in ("THE_ODDS_API_KEY", "KYRE_THE_ODDS_API_KEY"):
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    try:
        import streamlit as st
        for name in ("THE_ODDS_API_KEY", "KYRE_THE_ODDS_API_KEY"):
            value = str(st.secrets.get(name) or "").strip()
            if value:
                return value
    except Exception:
        pass
    return None


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

    Provider credentials stay server-side and are forwarded only to Kyre Sports
    API in a request header; the browser never receives them. Kyre Sports API
    remains the sole application-facing gateway and owns provider fallback.
    """
    provider_key = str(api_key or _default_the_odds_api_key() or "").strip()
    request_post = request_post or requests.post
    base_url = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    try:
        headers = {"X-Kyre-The-Odds-Api-Key": provider_key} if provider_key else {}
        response = request_post(
            f"{base_url}/api/v1/nba/pra/market",
            json={"date": slate_date.isoformat()},
            headers=headers,
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
