"""Deterministic Step-8 DATA_FIELD provenance certification."""
from __future__ import annotations

import cfb_top_picks_source_router_v1 as router


def _m(value, source, status="VERIFIED", note=""):
    return {
        "value": value, "status": status, "source": source,
        "observed_at": "2026-09-30T06:00:00+00:00", "note": note,
    }


def _detail():
    return {
        "offense_research": {
            "away": {"metrics": {
                "points_per_game": _m(31.0, "ESPN Core exact-team current-season statistics"),
                "yards_per_play": _m(6.1, "Checked-in 2026 CFB Step-3 verified snapshot fallback", "VERIFIED_FALLBACK"),
            }},
            "home": {"metrics": {
                "points_per_game": _m(28.0, "ESPN Core exact-team current-season statistics"),
                "red_zone_td_rate": _m(None, "", "UNAVAILABLE", "NCAA row unavailable and no verified team-official fallback"),
            }},
        },
        "defense_pace_research": {
            "away": {"metrics": {
                "points_allowed_per_game": _m(21.0, "ESPN exact-event completed-game summaries"),
                "plays_per_game": _m(72.0, "NCAA FBS Total Offense"),
            }},
            "home": {"metrics": {
                "points_allowed_per_game": _m(25.0, "Checked-in 2026 CFB Step-3 verified snapshot fallback", "VERIFIED_FALLBACK"),
                "plays_per_game": _m(68.0, "ESPN Core exact-team current-season statistics", "VERIFIED_FALLBACK"),
            }},
        },
        "market_reasoning": {
            "required_signals": ["offense_vs_defense_edge"],
            "signals": {"offense_vs_defense_edge": {
                "status": "VERIFIED", "text": "Verified edge.",
                "sources": ["ESPN Core exact-team current-season statistics"],
                "observed_at": "2026-09-30T06:00:00+00:00",
            }},
        },
        "benefits_risks": {
            "benefits": [{"status": "VERIFIED", "text": "Verified benefit.", "sources": ["NCAA FBS Total Offense"], "observed_at": "2026-09-30T06:00:00+00:00"}],
            "risks": [{"status": "VERIFIED", "text": "Verified risk.", "sources": ["ESPN exact-event completed-game summaries"], "observed_at": "2026-09-30T06:00:00+00:00"}],
        },
        "history_status": "VERIFIED_HISTORY",
        "history_source": "Winsipedia",
        "sources_verified": ["Winsipedia"],
        "history_observed_at": "2026-09-30T06:00:00+00:00",
    }


def main() -> int:
    result = router.build_source_freshness_audit({"market": "MONEYLINE"}, _detail())
    if result["status"] != "READY" or result["violation_count"] != 0:
        raise AssertionError(f"STEP8_AUDIT:{result['violations']}")
    if result["unit_of_work"] != "DATA_FIELD" or result["no_source_loyalty"] is not True:
        raise AssertionError("STEP8_ROUTER_DISCIPLINE")
    if result["fallback_used_count"] < 2:
        raise AssertionError("STEP8_FALLBACK_TRACKING")
    if not result["sources"] or result["material_fact_count"] < 8:
        raise AssertionError("STEP8_PROVENANCE_COUNTS")
    if result["projection_weight"] != 0.0 or result["sportsbook_projection_weight"] != 0.0:
        raise AssertionError("STEP8_WEIGHT")
    if result["may_modify_probability"] or result["may_modify_ranking"] or result["may_modify_selection"]:
        raise AssertionError("STEP8_MUTATION_FIREWALL")

    bad = _detail()
    bad["offense_research"]["away"]["metrics"]["points_per_game"]["source"] = ""
    blocked = router.build_source_freshness_audit({"market": "MONEYLINE"}, bad)
    if blocked["status"] != "BLOCKED" or blocked["violation_count"] < 1:
        raise AssertionError("STEP8_FAIL_CLOSED")

    print("CFB_TOP_PICKS_RESEARCH_V2_STEP8_DATA_FIELD_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP8_PROVENANCE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP8_FROZEN_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
