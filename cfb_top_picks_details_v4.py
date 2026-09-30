"""CFB Top Picks Research V2 Step 8 detail wrapper."""
from __future__ import annotations

from typing import Any, Mapping

import cfb_top_picks_details_v3 as prior
import cfb_top_picks_source_router_v1 as source_router

MODEL_VERSION = "CFB TOP PICKS DETAILS V4 • RESEARCH V2 STEP 8 SOURCE ROUTER"
SOURCE_ROUTER_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
API2_USED = False


def build_pick_detail(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    detail = dict(prior.build_pick_detail(row, slate_day))
    audit = source_router.build_source_freshness_audit(row, detail)
    detail["version"] = MODEL_VERSION
    detail["source_freshness_audit"] = audit
    detail["source_router_projection_weight"] = float(audit.get("projection_weight") or 0.0)
    return detail


__all__ = [
    "API2_USED", "MODEL_VERSION", "SOURCE_ROUTER_PROJECTION_WEIGHT",
    "SPORTSBOOK_PROJECTION_WEIGHT", "build_pick_detail",
]
