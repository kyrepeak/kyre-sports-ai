"""CFB Top Picks Research V2 Step 6 detail wrapper.

Additive over frozen cfb_top_picks_details_v1. Existing history, offense,
defense, pace, probability, and ranking behavior is preserved byte-for-byte.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_top_picks_details_v1 as prior
import cfb_top_picks_market_reasoning_v1 as market_reasoning

MODEL_VERSION = "CFB TOP PICKS DETAILS V2 • RESEARCH V2 STEP 6 MARKET REASONING"
MARKET_REASONING_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
API2_USED = False


def _series_from_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "history_ready": bool(detail.get("history_ready")),
        "status": str(detail.get("history_status") or ""),
        "source": str(detail.get("history_source") or ""),
        "sources_attempted": list(detail.get("sources_attempted") or []),
        "sources_verified": list(detail.get("sources_verified") or []),
        "observed_at": str(detail.get("history_observed_at") or ""),
        "meetings": int(detail.get("meetings") or 0),
        "away_wins": int(detail.get("away_wins") or 0),
        "home_wins": int(detail.get("home_wins") or 0),
        "ties": int(detail.get("ties") or 0),
        "avg_combined_total": float(detail.get("avg_combined_total") or 0.0),
        "series_record": dict(detail.get("series_record") or {}),
        "line_hit_context": dict(detail.get("line_hit_context") or {}),
    }


def build_pick_detail(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    detail = dict(prior.build_pick_detail(row, slate_day))
    if detail.get("ready") is not True:
        detail["market_reasoning"] = {
            "version": market_reasoning.MODEL_VERSION,
            "market": str(row.get("market") or "").upper(),
            "status": "IDENTITY_UNAVAILABLE",
            "required_signals": list(
                market_reasoning.REQUIRED_SIGNALS.get(str(row.get("market") or "").upper(), ())
            ),
            "signals": {},
            "summary": "Verified matchup identity is unavailable, so no market-specific research claim is added.",
            "projection_weight": 0.0,
            "sportsbook_projection_weight": 0.0,
            "may_modify_probability": False,
            "may_modify_ranking": False,
            "may_modify_selection": False,
            "api2_used": False,
        }
        detail["market_reasoning_projection_weight"] = 0.0
        return detail

    game = prior._verified_target_game(row, slate_day)
    reasoning = market_reasoning.build_market_reasoning(
        row,
        game,
        detail.get("offense_research") or {},
        detail.get("defense_pace_research") or {},
        _series_from_detail(detail),
    )
    detail["version"] = MODEL_VERSION
    detail["market_reasoning"] = reasoning
    detail["market_reasoning_projection_weight"] = float(reasoning.get("projection_weight") or 0.0)
    return detail


__all__ = [
    "API2_USED", "MARKET_REASONING_PROJECTION_WEIGHT", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_WEIGHT", "_series_from_detail", "build_pick_detail",
]
