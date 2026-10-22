"""Kyre Sports API CFB Top Picks Page 1 cleanup successor V4.

V4 preserves V3 ranking, price, probability and selection logic byte-for-byte by
calling the frozen V3 payload builder first. It only enriches visible identity
and presentation fields from NCAA and current official team rosters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query

import sports_api.api.cfb_top_picks_page1_v3 as v3
from sports_api.collectors.cfb_top_picks_identity_v1 import enrich_top_picks_payload

router = APIRouter(prefix="/api/v4/cfb/top-picks", tags=["cfb"])
MODEL_VERSION = "CFB TOP PICKS PAGE1 API V4 • CLEAN IDENTITY + PROFESSIONAL UI DATA"
SCHEMA_VERSION = "cfb_top_picks_page1_v4"
FORBIDDEN_PROVIDERS = ["SGO", "ESPN", "ESPN BET"]


def build_page1_payload(
    *,
    game_date: str | None = None,
    limit: int = 10,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    base = v3.build_page1_payload(game_date=game_date, limit=limit, now_provider=now_provider)
    enriched, identity_diag = enrich_top_picks_payload(base)
    enriched["schema_version"] = SCHEMA_VERSION
    enriched["model_version"] = MODEL_VERSION
    routing = dict(enriched.get("routing") or {})
    routing.update({
        "application_gateway": "Kyre Sports API",
        "team_identity_primary": "NCAA",
        "team_record_primary": "NCAA",
        "team_logo_primary": "NCAA",
        "player_identity_primary": "Official team athletics roster",
        "player_identity_scope": "final selected props only",
        "forbidden_providers": list(FORBIDDEN_PROVIDERS),
        "ranking_math_changed": False,
        "sportsbook_consensus_averaging": False,
        "fabrication": False,
        "null_to_zero": False,
    })
    enriched["routing"] = routing
    diagnostics = dict(enriched.get("diagnostics") or {})
    diagnostics["identity_enrichment"] = identity_diag
    diagnostics["v3_ranking_preserved"] = True
    enriched["diagnostics"] = diagnostics
    return enriched


@router.get("/page1")
def page1(
    game_date: str | None = Query(None, min_length=10, max_length=10),
    limit: int = Query(10, ge=1, le=10),
) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["FORBIDDEN_PROVIDERS", "MODEL_VERSION", "SCHEMA_VERSION", "build_page1_payload", "page1", "router"]
