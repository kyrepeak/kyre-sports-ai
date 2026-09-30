"""CFB Top Picks Research V2 Step 7 detail wrapper.

Additive over frozen Step 6 details. The Step-7 benefits/risks layer is read-only.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_top_picks_benefits_risks_v1 as benefits_risks
import cfb_top_picks_details_v2 as prior

MODEL_VERSION = "CFB TOP PICKS DETAILS V3 • RESEARCH V2 STEP 7 BENEFITS RISKS"
BENEFITS_RISKS_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
API2_USED = False


def build_pick_detail(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    detail = dict(prior.build_pick_detail(row, slate_day))
    result = benefits_risks.build_benefits_risks(row, detail)
    detail["version"] = MODEL_VERSION
    detail["benefits_risks"] = result
    detail["benefits_risks_projection_weight"] = float(result.get("projection_weight") or 0.0)
    return detail


__all__ = [
    "API2_USED", "BENEFITS_RISKS_PROJECTION_WEIGHT", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_WEIGHT", "build_pick_detail",
]
