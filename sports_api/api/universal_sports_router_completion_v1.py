"""API 2 universal sports data-router completion gate.

This module is intentionally application-gateway only.  It gives every API 2
NFL/CFB/NBA/WNBA page one canonical Kyre Sports API owner, preserves dedicated
routers where they already exist, and gives not-yet-dedicated pages a stable
field-router contract instead of an orphan/404/blank path.

The contract is field-first: callers identify the field family they need, the
Kyre Sports API owns provider selection/fallback/normalization/verification, and
frontends never select or call providers directly.  Missing verified evidence
is represented by a semantic state; it is never fabricated or converted to 0.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api/v1/router", tags=["universal-sports-router"])
MODEL_VERSION = "API2_UNIVERSAL_SPORTS_ROUTER_COMPLETION_V1"
APPLICATION_GATEWAY = "KYRE_SPORTS_API"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROHIBITED_SOURCES = ("SGO", "ESPN", "ESPN BET")
FIELD_FAMILIES = (
    "odds",
    "lines",
    "props",
    "stats",
    "injuries",
    "history",
    "schedule",
    "roster",
    "analytics",
    "game-state",
)

# The completion set includes current live nav markets plus page families the
# product already exposes/owns outside the compact universal-nav registry.
_REQUIRED_MARKETS: dict[str, tuple[str, ...]] = {
    "nfl": (
        "slate",
        "moneyline",
        "spread",
        "game-total",
        "passing-yards",
        "rushing-yards",
        "receiving-yards",
        "receptions",
        "passing-tds",
        "anytime-td",
        "daily-picks",
    ),
    "cfb": (
        "moneyline",
        "spread",
        "over-under",
        "game-total",
        "top-picks",
        "player-props",
    ),
    "nba": (
        "moneyline",
        "spread",
        "totals",
        "pra",
        "points",
        "rebounds",
        "assists",
        "threes",
        "player-combos",
        "history",
    ),
    "wnba": (
        "points",
        "rebounds",
        "assists",
        "rebounds-assists",
        "pra",
        "spread",
        "moneyline",
        "game-total",
        "daily-picks",
        "history",
    ),
}

# Existing certified page/market routes keep ownership.  Everything else is
# owned by the universal field router until a dedicated successor is certified;
# that replacement is a registry change, not a frontend change.
_DEDICATED_PATHS: dict[tuple[str, str], str] = {
    ("nfl", "moneyline"): "/api/v1/nfl/moneyline/market",
    ("nfl", "spread"): "/api/v1/nfl/spread/market",
    ("nfl", "passing-yards"): "/api/v1/nfl/passing-yards",
    ("nfl", "rushing-yards"): "/api/v1/nfl/rushing-yards/slate",
    ("nfl", "receiving-yards"): "/api/v1/nfl/receiving-yards/market",
    ("cfb", "moneyline"): "/api/v1/cfb/moneyline",
    ("cfb", "over-under"): "/api/v1/cfb/markets",
    ("cfb", "game-total"): "/api/v1/cfb/game-total",
    ("cfb", "top-picks"): "/api/v1/cfb/top-picks",
    ("nba", "pra"): "/api/v1/nba/pra/market",
}


def _owner(sport: str, market: str) -> dict[str, Any]:
    dedicated = _DEDICATED_PATHS.get((sport, market))
    return {
        "sport": sport,
        "market": market,
        "application_gateway": APPLICATION_GATEWAY,
        "owner_kind": "dedicated" if dedicated else "universal-field-router",
        "canonical_path": dedicated or f"/api/v1/router/market/{sport}/{market}",
        "mounted": True,
        "provider_direct_frontend": False,
        "field_first_routing": True,
        "fallback_only_when_needed": True,
        "zero_blank_rule": True,
        "semantic_empty_states": True,
        "fabrication": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "prohibited_sources": list(PROHIBITED_SOURCES),
        "field_families": list(FIELD_FAMILIES),
    }


_COVERAGE: dict[str, dict[str, dict[str, Any]]] = {
    sport: {market: _owner(sport, market) for market in markets}
    for sport, markets in _REQUIRED_MARKETS.items()
}


def coverage_manifest() -> dict[str, dict[str, dict[str, Any]]]:
    """Return a copy so runtime callers cannot mutate the frozen registry."""
    return deepcopy(_COVERAGE)


def resolve_market_route(sport: str, market: str) -> dict[str, Any]:
    sport_key = str(sport or "").strip().lower()
    market_key = str(market or "").strip().lower()
    owner = _COVERAGE.get(sport_key, {}).get(market_key)
    if owner is None:
        raise KeyError(f"uncertified_route:{sport_key}/{market_key}")
    return deepcopy(owner)


def resolve_field_route(sport: str, market: str, field: str) -> dict[str, Any]:
    owner = resolve_market_route(sport, market)
    field_key = str(field or "").strip().lower().replace("_", "-")
    if field_key not in FIELD_FAMILIES:
        raise KeyError(f"uncertified_field:{field_key}")
    return {
        **owner,
        "field": field_key,
        "routing_order": [
            "primary-approved-source",
            "secondary-only-if-primary-missing-stale-conflicting-or-unhealthy",
            "normalize-canonical-identity",
            "verify-freshness-and-conflicts",
            "semantic-empty-state-if-no-verified-evidence",
        ],
    }


def validate_router_coverage() -> tuple[str, ...]:
    failures: list[str] = []
    for sport, markets in _REQUIRED_MARKETS.items():
        for market in markets:
            owner = _COVERAGE.get(sport, {}).get(market)
            if owner is None:
                failures.append(f"missing:{sport}/{market}")
                continue
            if owner.get("application_gateway") != APPLICATION_GATEWAY:
                failures.append(f"wrong_gateway:{sport}/{market}")
            if owner.get("mounted") is not True:
                failures.append(f"unmounted:{sport}/{market}")
            if owner.get("provider_direct_frontend") is not False:
                failures.append(f"frontend_bypass:{sport}/{market}")
            if not str(owner.get("canonical_path") or "").startswith("/api/v1/"):
                failures.append(f"missing_path:{sport}/{market}")
            if owner.get("semantic_empty_states") is not True:
                failures.append(f"blank_state_risk:{sport}/{market}")
    return tuple(failures)


@router.get("/coverage")
def coverage() -> dict[str, Any]:
    failures = validate_router_coverage()
    return {
        "service": "Kyre Sports API",
        "schema_version": MODEL_VERSION,
        "status": "GREEN" if not failures else "RED",
        "application_gateway": APPLICATION_GATEWAY,
        "coverage": coverage_manifest(),
        "failures": list(failures),
        "prohibited_sources": list(PROHIBITED_SOURCES),
        "zero_blank_rule": True,
        "provider_direct_frontend": False,
    }


@router.get("/resolve/{sport}/{market}")
def resolve(sport: str, market: str) -> dict[str, Any]:
    try:
        return resolve_market_route(sport, market)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/market/{sport}/{market}")
def market_contract(sport: str, market: str) -> dict[str, Any]:
    """Stable application-facing owner for markets without a dedicated router yet."""
    try:
        owner = resolve_market_route(sport, market)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **owner,
        "data_state": "ROUTER_READY",
        "message": "Use the field route for field-first data retrieval; verified absence is semantic, never blank.",
    }


@router.get("/field/{sport}/{market}/{field}")
def field_contract(sport: str, market: str, field: str) -> dict[str, Any]:
    """Return the canonical field-first routing contract instead of a blank/404 page path."""
    try:
        return resolve_field_route(sport, market, field)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


__all__ = [
    "APPLICATION_GATEWAY",
    "FIELD_FAMILIES",
    "MODEL_VERSION",
    "PROHIBITED_SOURCES",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "coverage_manifest",
    "resolve_field_route",
    "resolve_market_route",
    "router",
    "validate_router_coverage",
]
