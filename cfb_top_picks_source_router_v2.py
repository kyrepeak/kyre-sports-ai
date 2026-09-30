"""CFB Top Picks Research V2 Step 9 — final provenance closeout wrapper.

Preserves frozen Step-8 routing and supplies the historical attempt alias that
Step 8's audit expects for non-history terminal states. No data values change.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_top_picks_source_router_v1 as prior

MODEL_VERSION = "CFB TOP PICKS SOURCE ROUTER V2 • STEP 9 FINAL CERT CLOSEOUT"
SOURCE_ROUTER_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
API2_USED = False


def build_source_freshness_audit(
    row: Mapping[str, Any],
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = dict(detail)
    if "source_attempts" not in normalized:
        normalized["source_attempts"] = list(normalized.get("sources_attempted") or [])
    result = dict(prior.build_source_freshness_audit(row, normalized))
    result["version"] = MODEL_VERSION
    result["projection_weight"] = 0.0
    result["sportsbook_projection_weight"] = 0.0
    result["may_modify_probability"] = False
    result["may_modify_ranking"] = False
    result["may_modify_selection"] = False
    result["api2_used"] = False
    return result


__all__ = [
    "API2_USED", "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION", "MODEL_VERSION",
    "SOURCE_ROUTER_PROJECTION_WEIGHT", "SPORTSBOOK_PROJECTION_WEIGHT",
    "build_source_freshness_audit",
]
