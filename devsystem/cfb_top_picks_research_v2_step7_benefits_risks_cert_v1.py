"""Deterministic certification for CFB Top Picks Research V2 Step 7."""
from __future__ import annotations

import cfb_top_picks_benefits_risks_v1 as br


def _metric(value, source):
    return {"value": value, "status": "VERIFIED", "source": source, "observed_at": "2026-09-30T05:00:00+00:00"}


def _base_detail():
    return {
        "ready": True,
        "market_reasoning": {"observed_at": "2026-09-30T05:00:00+00:00"},
        "offense_research": {
            "away": {
                "observed_at": "2026-09-30T05:00:00+00:00",
                "metrics": {
                    "points_per_game": _metric(34.0, "ESPN offense"),
                    "recent_scoring_avg": _metric(28.0, "ESPN recent"),
                },
                "recent_games": [
                    {"points_for": 31, "points_against": 28},
                    {"points_for": 27, "points_against": 24},
                ],
                "source_router": {"recent_scoring": {"provider": "ESPN completed games"}},
            },
            "home": {
                "observed_at": "2026-09-30T05:00:00+00:00",
                "metrics": {
                    "points_per_game": _metric(29.0, "ESPN offense"),
                    "recent_scoring_avg": _metric(30.0, "ESPN recent"),
                },
                "recent_games": [
                    {"points_for": 35, "points_against": 27},
                    {"points_for": 30, "points_against": 24},
                ],
                "source_router": {"recent_scoring": {"provider": "ESPN completed games"}},
            },
        },
        "defense_pace_research": {
            "away": {"metrics": {"recent_points_allowed_avg": _metric(24.0, "ESPN defense")}},
            "home": {"metrics": {"recent_points_allowed_avg": _metric(27.0, "ESPN defense")}},
        },
        "history_ready": True,
        "history_status": "VERIFIED_HISTORY",
        "history_source": "Verified series source",
        "sources_verified": ["Verified series source"],
        "history_observed_at": "2026-09-30T05:00:00+00:00",
        "meetings": 4,
        "away_wins": 1,
        "home_wins": 3,
        "avg_combined_total": 65.0,
    }


def _row(market, pick, probability=.66):
    return {
        "market": market,
        "pick": pick,
        "away": "Away State",
        "home": "Home Tech",
        "probability": int(probability * 100),
        "probability_value": probability,
        "source": "Frozen Top Picks model",
    }


def _assert_evidence(result):
    if not result["benefits"] or not result["risks"]:
        raise AssertionError("STEP7_BENEFIT_RISK_EMPTY")
    for bucket in ("benefits", "risks"):
        for item in result[bucket]:
            if not str(item.get("text") or "").strip():
                raise AssertionError(f"STEP7_TEXT:{bucket}")
            if not item.get("sources"):
                raise AssertionError(f"STEP7_SOURCE:{bucket}:{item}")
            if not str(item.get("observed_at") or "").strip():
                raise AssertionError(f"STEP7_FRESHNESS:{bucket}:{item}")
    if result["projection_weight"] != 0.0 or result["sportsbook_projection_weight"] != 0.0:
        raise AssertionError("STEP7_WEIGHT")
    if result["may_modify_probability"] or result["may_modify_ranking"] or result["may_modify_selection"]:
        raise AssertionError("STEP7_MUTATION_FIREWALL")


def main() -> int:
    total_detail = _base_detail()
    total = br.build_benefits_risks(_row("OVER/UNDER", "Over 60.5"), total_detail)
    _assert_evidence(total)
    if total["football_benefit_count"] < 1 or total["football_risk_count"] < 1:
        raise AssertionError("STEP7_TOTAL_FOOTBALL_BALANCE")

    spread_detail = _base_detail()
    spread = br.build_benefits_risks(_row("SPREAD", "Away State +3.5", .64), spread_detail)
    _assert_evidence(spread)
    if spread["football_benefit_count"] < 1 or spread["football_risk_count"] < 1:
        raise AssertionError("STEP7_SPREAD_FOOTBALL_BALANCE")

    ml_detail = _base_detail()
    moneyline = br.build_benefits_risks(_row("MONEYLINE", "Away State", .69), ml_detail)
    _assert_evidence(moneyline)
    if moneyline["football_benefit_count"] < 1 or moneyline["football_risk_count"] < 1:
        raise AssertionError("STEP7_ML_FOOTBALL_BALANCE")

    unavailable = br.build_benefits_risks(
        _row("MONEYLINE", "Away State"),
        {"ready": False, "market_reasoning": {"observed_at": "2026-09-30T05:00:00+00:00"}},
    )
    if unavailable["status"] != "IDENTITY_UNAVAILABLE" or unavailable["benefits"] or unavailable["risks"]:
        raise AssertionError("STEP7_FAIL_CLOSED")

    print("CFB_TOP_PICKS_RESEARCH_V2_STEP7_THREE_MARKETS_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP7_VERIFIED_EVIDENCE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP7_FROZEN_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
