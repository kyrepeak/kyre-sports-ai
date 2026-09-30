"""CFB Top Picks Research V2 Step 9 — final detail certification wrapper."""
from __future__ import annotations

from typing import Any, Mapping

import cfb_top_picks_details_v4 as prior
import cfb_top_picks_source_router_v2 as source_router

MODEL_VERSION = "CFB TOP PICKS DETAILS V5 • RESEARCH V2 STEP 9 FINAL CERT"
FINAL_CERT_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
API2_USED = False


def build_pick_detail(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    detail = dict(prior.build_pick_detail(row, slate_day))
    detail["source_freshness_audit"] = source_router.build_source_freshness_audit(row, detail)
    detail["version"] = MODEL_VERSION
    detail["final_cert_projection_weight"] = 0.0
    return detail


__all__ = [
    "API2_USED", "FINAL_CERT_PROJECTION_WEIGHT", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_WEIGHT", "build_pick_detail",
]
