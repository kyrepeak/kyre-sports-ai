"""CFB Top Picks Repair Mission Step 1 — history alias regression guard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "cfb_top_picks_history_router_v1.py"
TEST = ROOT / "tests/test_cfb_top_picks_history_router_repair_step1_v1.py"


class CFBTopPicksHistoryRepairStep1Failure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    router = ROUTER.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    failures: list[str] = []

    for token in (
        "def _winsipedia_lookup_name",
        'return re.sub(r"\\bSt\\.?$", "State", text, flags=re.IGNORECASE)',
        "wins_away_lookup = _winsipedia_lookup_name(away, away_id)",
        "wins_home_lookup = _winsipedia_lookup_name(home, home_id)",
        "recovery._fetch_winsipedia_games(",
        '"winsipedia_lookup_name"',
        '"lookup_names"',
        "HISTORY_PROJECTION_WEIGHT = 0.0",
        "HISTORY_SELECTION_WEIGHT = 0.0",
        "HISTORY_RANKING_WEIGHT = 0.0",
        "SPORTSBOOK_PROJECTION_WEIGHT = 0.0",
        "API2_USED = False",
    ):
        if token not in router:
            failures.append(f"history repair missing {token}")

    for token in (
        "Florida St.",
        "Florida State",
        'calls == [("Virginia", "Florida State")]',
        'out["status"] == history.VERIFIED_HISTORY',
        'out["canonical_aliases"]["home"]["winsipedia_slug"] == "florida-state"',
    ):
        if token not in test:
            failures.append(f"permanent regression test missing {token}")

    if "cfb_over_under_data_recovery_v1" not in router:
        failures.append("frozen recovery dependency unexpectedly removed")
    if "sports_api" in router or "/api/v1/" in router:
        failures.append("history repair illegally coupled API 2")

    if failures:
        raise CFBTopPicksHistoryRepairStep1Failure(" | ".join(failures))

    return {
        "status": "GREEN",
        "mission_step": "1/5",
        "repair": "winsipedia_display_alias_canonicalization",
        "florida_st_to_florida_state": True,
        "shared_ou_recovery_modified": False,
        "projection_weight": 0.0,
        "ranking_weight": 0.0,
        "selection_weight": 0.0,
        "api2_protected": True,
        "regression_debt_guard": "PERMANENT_TEST_AND_CONTRACT",
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_REPAIR_STEP1_HISTORY_ALIAS_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
