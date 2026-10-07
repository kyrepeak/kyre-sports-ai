from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "wnba_players_v25.py"
GATE = ROOT / "wnba_data_completeness_repair_v1_step2_stats_gate.py"
TEST = ROOT / "tests" / "test_wnba_data_completeness_repair_v1_step2.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    owner = OWNER.read_text()
    gate = GATE.read_text()
    test = TEST.read_text()

    compile(owner, str(OWNER), "exec")
    compile(gate, str(GATE), "exec")
    compile(test, str(TEST), "exec")

    require(
        "from wnba_data_completeness_repair_v1_step2_stats_gate import gate_primary_production" in owner,
        "STEP2_GATE_IMPORT_MISSING",
    )
    require(
        "primary = gate_primary_production(primary, roster, team_ids)" in owner,
        "STEP2_GATE_CALL_MISSING",
    )
    require("overlaps = sum(" not in owner, "STEP2_PARTIAL_ID_OVERLAP_GATE_STILL_PRESENT")
    require("def gate_primary_production(" in gate, "STEP2_GATE_FUNCTION_MISSING")
    require("or (bool(name) and (tid, name) in allowed_names)" in gate, "STEP2_NAME_MATCH_MISSING")
    require("if tid not in roster_teams:" in gate and "keep.append(True)" in gate, "STEP2_MISSING_ROSTER_PRESERVATION_MISSING")
    require("never changes" in gate and "stat values" in gate, "STEP2_STAT_IMMUTABILITY_CONTRACT_MISSING")
    require("test_partial_provider_id_overlap_preserves_name_matched_production_and_stats" in test, "STEP2_MIXED_ID_TEST_MISSING")
    require("test_missing_team_roster_feed_preserves_league_guarded_production" in test, "STEP2_ROSTER_FAILURE_TEST_MISSING")
    require("test_gate_never_introduces_a_new_slate_team" in test, "STEP2_SLATE_ISOLATION_TEST_MISSING")

    print("WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_CERT_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
