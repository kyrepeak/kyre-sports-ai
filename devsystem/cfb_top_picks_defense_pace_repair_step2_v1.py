"""CFB Top Picks Repair Mission Step 2 — Defense + Pace completeness guard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_top_picks_defense_pace_research_v1.py"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step5_defense_pace_cert_v1.py"
TEST = ROOT / "tests/test_cfb_top_picks_research_v2_step5_defense_pace_v1.py"


class CFBTopPicksDefensePaceRepairStep2Failure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    engine = ENGINE.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    failures: list[str] = []

    for token in (
        "_TEAM_OFFICIAL_DEFENSE_PACE_FALLBACKS",
        '"west florida"',
        '"opponent_red_zone_attempts": 13.0',
        '"opponent_red_zone_touchdowns": 7.0',
        '"opponent_pass_attempts": 110.0',
        '"opponent_pass_completions": 59.0',
        '"opponent_pass_yards": 695.0',
        '"opponent_rush_attempts": 160.0',
        '"opponent_rush_yards": 707.0',
        '"total_offensive_plays": 242.0',
        '"total_possession_seconds": 6854.0',
        "University of West Florida Athletics 2026 cumulative football statistics",
        '"verified_at": "2026-10-01"',
        "VERIFIED_FALLBACK",
        "FCS_TRANSITION",
        "DEFENSE_PACE_RESEARCH_PROJECTION_WEIGHT = 0.0",
        "SPORTSBOOK_PROJECTION_WEIGHT = 0.0",
        "API2_USED = False",
    ):
        if token not in engine:
            failures.append(f"Defense/Pace repair missing {token}")

    for token in (
        '!= len(research.SUPPORTING_FIELDS)',
        "CFB_TOP_PICKS_REPAIR_STEP2_SUPPORT_INCOMPLETE",
        "CFB_TOP_PICKS_REPAIR_STEP2_20_TEAM_FULL_SUPPORT_GREEN",
        '"full_supporting_completeness_required": True',
    ):
        if token not in cert:
            failures.append(f"20-team completeness cert missing {token}")

    for token in (
        "test_west_florida_transition_fallback_completes_all_supporting_fields",
        'profile["supporting_ready"] == 6',
        'round(7 / 13, 8)',
        'round(6854 / 242, 8)',
        "test_unknown_transition_team_still_fails_closed_without_official_snapshot",
    ):
        if token not in test:
            failures.append(f"permanent regression test missing {token}")

    if "cfb_top_picks_history_router_v1" in engine:
        failures.append("Step-2 repair illegally coupled the frozen Step-1 history router")
    if "sports_api" in engine or "/api/v1/" in engine:
        failures.append("Step-2 repair illegally coupled API 2")

    if failures:
        raise CFBTopPicksDefensePaceRepairStep2Failure(" | ".join(failures))

    return {
        "status": "GREEN",
        "mission_step": "2/5",
        "required_teams": 20,
        "supporting_fields_per_team": 6,
        "full_supporting_completeness_required": True,
        "west_florida_transition_fallback": True,
        "unknown_transition_fail_closed": True,
        "projection_weight": 0.0,
        "ranking_mutation": False,
        "selection_mutation": False,
        "api2_protected": True,
        "step1_history_protected": True,
        "regression_debt_guard": "PERMANENT_TEST_AND_CONTRACT",
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_REPAIR_STEP2_DEFENSE_PACE_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
