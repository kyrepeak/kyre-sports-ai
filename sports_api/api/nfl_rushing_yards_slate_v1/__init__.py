"""Rushing Yards V1 successor overlay for field-level availability semantics.

The underlying slate implementation remains the authoritative data builder. This
package post-processes only availability/routing metadata so an active RB card
never exposes a vague blank when no approved injury provider is wired into the
current deployment. It does not invent an injury designation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_rushing_yards_slate_v1.py"
_SPEC = importlib.util.spec_from_file_location("sports_api.api._nfl_rushing_yards_slate_v1_base", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Rushing Yards slate base implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

# The canonical builder stays authoritative, but its request-time transport is
# bounded so a cold serverless request cannot download multi-season PBP or wait
# indefinitely on direct-book enrichment before Page 1 can render.
from sports_api import nfl_rushing_yards_fastpath_v1 as _fastpath

_fastpath.install(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__", "router", "slate", "status", "build_slate_bundle"}:
        globals().setdefault(_name, _value)

SCHEMA_VERSION = _legacy.SCHEMA_VERSION
SERVICE = _legacy.SERVICE
GATEWAY = _legacy.GATEWAY

# These are approved by policy, but no credentialed/integrated injury connector is
# present in the current Kyre Sports API deployment. The state is explicit so a
# missing injury designation cannot masquerade as "healthy" or as a zero value.
INJURY_PROVIDER_AUDIT = (
    {"provider": "Official NFL/team injury reports", "state": "NOT_INTEGRATED_IN_CURRENT_DEPLOYMENT"},
    {"provider": "Sportradar", "state": "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"},
    {"provider": "SportsDataIO", "state": "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"},
    {"provider": "RotoWire", "state": "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"},
)
MARKET_PROVIDER_AUDIT = (
    {"provider": "OpticOdds", "state": "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"},
    {"provider": "The Odds API", "state": "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"},
    {"provider": "SportsDataIO", "state": "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"},
    {"provider": "Direct sportsbook", "state": "ACTIVE_FIELD_SOURCE"},
)


def availability_state_for_active_roster() -> dict[str, Any]:
    return {
        "status": "ACTIVE_ROSTER_VERIFIED_INJURY_DESIGNATION_UNRESOLVED",
        "display": "Active roster · injury designation not verified",
        "roster_status": "ACTIVE",
        "roster_verified": True,
        "injury_designation": None,
        "injury_designation_verified": False,
        "resolution_state": "NO_CONFIGURED_APPROVED_INJURY_PROVIDER",
        "provider_attempts": [dict(row) for row in INJURY_PROVIDER_AUDIT],
        "missing_to_zero": False,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    cards: list[dict[str, Any]] = []
    for raw in payload.get("running_backs") or []:
        if not isinstance(raw, dict):
            continue
        card = dict(raw)
        detail = dict(card.get("detail") or {})
        # Every selected player entered the base slate through the active verified
        # roster gate. Preserve that fact while refusing to infer injury health.
        detail["availability"] = availability_state_for_active_roster()
        lineage = dict(detail.get("source_lineage") or {})
        lineage["availability_roster"] = "nflverse weekly roster active-status verification"
        lineage["injury_designation"] = "no configured approved injury provider; no designation fabricated"
        detail["source_lineage"] = lineage
        card["detail"] = detail
        cards.append(card)
    out["running_backs"] = cards
    out["running_back_count"] = len(cards)
    routing = dict(out.get("routing") or {})
    routing["availability_field_policy"] = {
        "active_roster_is_not_injury_clearance": True,
        "provider_audit": [dict(row) for row in INJURY_PROVIDER_AUDIT],
        "unverified_injury_designation_to_zero": False,
        "semantic_state": "ACTIVE_ROSTER_VERIFIED_INJURY_DESIGNATION_UNRESOLVED",
    }
    routing["market_field_policy"] = {
        "provider_audit": [dict(row) for row in MARKET_PROVIDER_AUDIT],
        "book_specific_records": True,
        "sportsbook_line_averaging": False,
        "unposted_market_state": "MARKET_NOT_POSTED",
    }
    routing["request_time_transport_policy"] = {
        "full_pbp_downloads": False,
        "weekly_player_summaries": True,
        "current_stats_roster_history_prewarm": "CONCURRENT",
        "prefetch_budget_seconds": _fastpath.PREFETCH_BUDGET_SECONDS,
        "player_stats_timeout_seconds": _fastpath.PLAYER_STATS_TIMEOUT_SECONDS,
        "roster_timeout_seconds": _fastpath.ROSTER_TIMEOUT_SECONDS,
        "history_budget_seconds": _fastpath.HISTORY_BUDGET_SECONDS,
        "market_budget_seconds": _fastpath.MARKET_BUDGET_SECONDS,
        "market_call_timeout_seconds": _fastpath.MARKET_CALL_TIMEOUT_SECONDS,
        "slow_enrichment_blocks_slate": False,
    }
    out["routing"] = routing
    return out


def build_slate_bundle(*, target_date: str | None = None, now_et: Any = None) -> dict[str, Any]:
    _fastpath.prewarm_request_inputs(_legacy, target_date=target_date, now_et=now_et)
    return _postprocess_payload(_legacy.build_slate_bundle(target_date=target_date, now_et=now_et))


router = APIRouter(prefix="/api/v1/nfl/rushing-yards/slate", tags=["nfl-rushing-yards-slate"])


@router.get("/status")
def status() -> dict[str, Any]:
    base = dict(_legacy.status())
    base["availability_semantics"] = {
        "active_roster_verified": True,
        "injury_designation_fabrication": False,
        "provider_audit": [dict(row) for row in INJURY_PROVIDER_AUDIT],
    }
    base["market_provider_audit"] = [dict(row) for row in MARKET_PROVIDER_AUDIT]
    base["request_time_transport_policy"] = {
        "full_pbp_downloads": False,
        "weekly_player_summaries": True,
        "current_stats_roster_history_prewarm": "CONCURRENT",
        "prefetch_budget_seconds": _fastpath.PREFETCH_BUDGET_SECONDS,
        "player_stats_timeout_seconds": _fastpath.PLAYER_STATS_TIMEOUT_SECONDS,
        "roster_timeout_seconds": _fastpath.ROSTER_TIMEOUT_SECONDS,
        "history_budget_seconds": _fastpath.HISTORY_BUDGET_SECONDS,
        "market_budget_seconds": _fastpath.MARKET_BUDGET_SECONDS,
        "market_call_timeout_seconds": _fastpath.MARKET_CALL_TIMEOUT_SECONDS,
        "slow_enrichment_blocks_slate": False,
    }
    return base


@router.get("")
def slate(date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict[str, Any]:
    return build_slate_bundle(target_date=date)


__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {
    "INJURY_PROVIDER_AUDIT",
    "MARKET_PROVIDER_AUDIT",
    "availability_state_for_active_roster",
    "build_slate_bundle",
    "router",
    "slate",
    "status",
})
