from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "wnba_availability_v27.py"
TEST = ROOT / "tests/test_wnba_data_completeness_repair_v1_step2_selected_day_handoff.py"
TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_SELECTED_DAY_HANDOFF_GREEN"


def main() -> int:
    owner = OWNER.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    required_owner = "raw, _ = players._build_selected_player_pool(day_str)"
    forbidden_owner = "raw = players.player_form_table(pd.to_datetime(day_str).year)"
    required_test = "test_verified_pool_hydrates_the_exact_requested_day"
    if required_owner not in owner:
        raise SystemExit("STEP2_SELECTED_DAY_OWNER_MISSING")
    if forbidden_owner in owner:
        raise SystemExit("STEP2_YEAR_ONLY_HANDOFF_STILL_PRESENT")
    if required_test not in test:
        raise SystemExit("STEP2_SELECTED_DAY_TEST_MISSING")
    print(TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
