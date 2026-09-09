"""CFB Over/Under live market adapter — odds integration Step 4.

Reads the production Step 3 CFB odds contract and attaches identity-verified
sportsbook totals to the already-frozen Streamlit schedule rows.

This module does not alter any projection formula. The market total is an
analysis threshold/context value only and carries 0% projection weight.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Any, Mapping

import requests
import streamlit as st

MODEL_VERSION = "CFB O/U MARKET ADAPTER V1 • ODDS INTEGRATION STEP 4"
API_BASE_ENV = "KYRE_SPORTS_API_BASE_URL"
DEFAULT_API_BASE = "https://kyre-sports-api.onrender.com"
API_PATH = "/api/v1/cfb/odds"
REQUEST_TIMEOUT_SECONDS = 20.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _api_base() -> str:
    configured = _clean(os.environ.get(API_BASE_ENV))
    return (configured or DEFAULT_API_BASE).rstrip("/")


def _safe_day(value: Any) -> str:
    text = _clean(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("CFB odds date must be YYYY-MM-DD")
    return text


def _validate_payload(payload: Any, *, requested_day: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("CFB odds API returned a non-object payload")
    if int(payload.get("step") or 0) != 3:
        raise ValueError("CFB odds API Step 3 contract is unavailable")
    if _clean(payload.get("schema_version")) != "cfb_odds_v1":
        raise ValueError("CFB odds API schema is not cfb_odds_v1")

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise ValueError("CFB odds API diagnostics are missing")
    if diagnostics.get("complete_identity_coverage") is not True:
        raise ValueError("CFB odds API identity coverage is incomplete")
    if int(diagnostics.get("unmatched_market_rows") or 0) != 0:
        raise ValueError("CFB odds API contains unmatched market rows")
    if diagnostics.get("synthetic_official_ids") is not False:
        raise ValueError("CFB odds API synthetic-ID policy is unsafe")
    if diagnostics.get("fuzzy_matching") is not False:
        raise ValueError("CFB odds API fuzzy identity policy is unsafe")

    semantics = payload.get("market_semantics")
    if not isinstance(semantics, Mapping):
        raise ValueError("CFB odds API market semantics are missing")
    if float(semantics.get("projection_weight") or 0.0) != 0.0:
        raise ValueError("CFB market projection weight must remain 0")
    if semantics.get("market_context_only") is not True:
        raise ValueError("CFB market feed must remain context-only")
    if semantics.get("may_modify_projection") is not False:
        raise ValueError("CFB market feed may not modify projection")

    rows = payload.get("games")
    if not isinstance(rows, list):
        raise ValueError("CFB odds API games must be a list")

    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("CFB odds API contains a malformed game row")
        game_id = _clean(raw.get("game_id"))
        day = _clean(raw.get("game_date"))
        if not game_id:
            raise ValueError("CFB odds API row is missing official game_id")
        if day != requested_day:
            raise ValueError("CFB odds API returned a row outside the requested date")
        if raw.get("identity_verified") is not True:
            raise ValueError("CFB odds API returned a non-verified identity")
        if game_id in seen:
            raise ValueError("CFB odds API returned duplicate official game IDs")
        seen.add(game_id)

        try:
            total = float(raw.get("total"))
        except (TypeError, ValueError) as exc:
            raise ValueError("CFB odds API total is not numeric") from exc
        if not 20.0 <= total <= 100.0:
            raise ValueError("CFB odds API total is outside the supported UI range")

        validated.append(
            {
                "game_id": game_id,
                "provider_game_id": _clean(raw.get("provider_game_id")),
                "game_date": day,
                "away_team": _clean(raw.get("away_team")),
                "home_team": _clean(raw.get("home_team")),
                "away_team_id": _clean(raw.get("away_team_id")),
                "home_team_id": _clean(raw.get("home_team_id")),
                "start_time_utc": _clean(raw.get("start_time_utc")),
                "sportsbook": _clean(raw.get("sportsbook")),
                "market_type": _clean(raw.get("market_type")),
                "total": total,
                "line_status": _clean(raw.get("line_status")),
                "line_updated_at_utc": _clean(raw.get("line_updated_at_utc")),
                "venue": _clean(raw.get("venue")),
                "broadcast": _clean(raw.get("broadcast")),
                "identity_verified": True,
            }
        )

    return {
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "captured_at_utc": _clean(payload.get("captured_at_utc")),
        "source": _clean(payload.get("source")),
        "game_count": len(validated),
        "games": validated,
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "diagnostics": dict(diagnostics),
    }


@st.cache_data(ttl=90, show_spinner=False)
def load_odds_for_date(
    target_date: Any,
    sportsbook: str = "FanDuel",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch one identity-verified CFB game-total slate from the live API."""
    day = _safe_day(target_date)
    book = _clean(sportsbook) or "FanDuel"
    url = _api_base() + API_PATH
    try:
        response = requests.get(
            url,
            params={"game_date": day, "sportsbook": book},
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "User-Agent": "KyreSportsAI-Streamlit-CFB-Step4/1.0",
            },
        )
        status_code = int(response.status_code)
        response.raise_for_status()
        payload = _validate_payload(response.json(), requested_day=day)
        return payload, {
            "status": "GREEN",
            "http": status_code,
            "requested_date": day,
            "sportsbook": book,
            "api_base": _api_base(),
            "game_count": len(payload["games"]),
            "identity_verified_rows": len(payload["games"]),
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "error": "",
        }
    except Exception as exc:
        # Missing/unreachable market data is visible and fail-closed. The frozen
        # projection stack remains usable through its manual threshold fallback.
        return {
            "step": 3,
            "schema_version": "cfb_odds_v1",
            "captured_at_utc": "",
            "source": "",
            "game_count": 0,
            "games": [],
            "market_semantics": {
                "projection_weight": 0.0,
                "market_context_only": True,
                "may_modify_projection": False,
            },
        }, {
            "status": "UNAVAILABLE",
            "http": None,
            "requested_date": day,
            "sportsbook": book,
            "api_base": _api_base(),
            "game_count": 0,
            "identity_verified_rows": 0,
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }


def attach_market_lines(
    games: list[Mapping[str, Any]],
    odds_payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach market fields by official ESPN event ID only.

    No fuzzy/team-name reconciliation occurs in Streamlit. Step 2 already owns
    identity reconciliation, and Step 3 exposes the verified official game ID.
    """
    rows = odds_payload.get("games") if isinstance(odds_payload, Mapping) else []
    market_by_id: dict[str, Mapping[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping) or row.get("identity_verified") is not True:
                continue
            game_id = _clean(row.get("game_id"))
            if game_id:
                market_by_id[game_id] = row

    out: list[dict[str, Any]] = []
    matched = 0
    missing_identity = 0
    missing_market = 0

    for raw in games:
        game = dict(raw)
        official_id = _clean(game.get("espn_event_id"))
        if not official_id:
            missing_identity += 1
            game.update(
                {
                    "market_line_available": False,
                    "market_identity_verified": False,
                    "market_reason": "missing_official_espn_event_id",
                    "market_projection_weight": 0.0,
                }
            )
            out.append(game)
            continue

        market = market_by_id.get(official_id)
        if market is None:
            missing_market += 1
            game.update(
                {
                    "market_line_available": False,
                    "market_identity_verified": True,
                    "market_reason": "no_current_market_row_for_official_game_id",
                    "market_projection_weight": 0.0,
                }
            )
            out.append(game)
            continue

        game.update(
            {
                "market_line_available": True,
                "market_identity_verified": True,
                "market_reason": "",
                "market_official_game_id": official_id,
                "market_provider_game_id": _clean(market.get("provider_game_id")),
                "market_total": float(market["total"]),
                "market_sportsbook": _clean(market.get("sportsbook")),
                "market_status": _clean(market.get("line_status")),
                "market_updated_at_utc": _clean(market.get("line_updated_at_utc")),
                "market_captured_at_utc": _clean(odds_payload.get("captured_at_utc")),
                "market_source": _clean(odds_payload.get("source")),
                "market_projection_weight": 0.0,
                "market_context_only": True,
                "market_may_modify_projection": False,
            }
        )
        matched += 1
        out.append(game)

    return out, {
        "version": MODEL_VERSION,
        "schedule_games": len(games),
        "api_market_rows": len(market_by_id),
        "market_lines_attached": matched,
        "schedule_games_missing_official_id": missing_identity,
        "schedule_games_without_market": missing_market,
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "matching_method": "official ESPN event_id only",
        "fuzzy_matching": False,
        "synthetic_ids": False,
    }


def market_line(game: Mapping[str, Any]) -> float | None:
    if game.get("market_line_available") is not True:
        return None
    try:
        value = float(game.get("market_total"))
    except (TypeError, ValueError):
        return None
    return value if 20.0 <= value <= 100.0 else None


def clear_market_cache() -> None:
    try:
        load_odds_for_date.clear()
    except Exception:
        pass


__all__ = [
    "API_BASE_ENV",
    "API_PATH",
    "DEFAULT_API_BASE",
    "MODEL_VERSION",
    "attach_market_lines",
    "clear_market_cache",
    "load_odds_for_date",
    "market_line",
]
