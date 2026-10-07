from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "sports_api" / "wnba_pra_speed_v3_step3_espn_history.py"
TEST = ROOT / "tests" / "test_wnba_data_completeness_repair_v1_step2_rebound_alias.py"
TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_REBOUND_ALIAS_GREEN"


def main() -> int:
    owner = OWNER.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    required_owner = '"rebounds": _to_int(_pick(stats, "REB", "rebounds", "totalRebounds")),'
    forbidden_owner = '"rebounds": _to_int(_pick(stats, "REB", "rebounds")),'
    if required_owner not in owner:
        raise SystemExit("STEP2_REBOUND_TOTAL_REBOUNDS_ALIAS_MISSING")
    if forbidden_owner in owner:
        raise SystemExit("STEP2_REBOUND_OLD_ALIAS_ONLY_EXPRESSION_PRESENT")
    if "test_live_espn_total_rebounds_alias_is_preserved" not in test:
        raise SystemExit("STEP2_REBOUND_ALIAS_TEST_MISSING")
    print(TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
