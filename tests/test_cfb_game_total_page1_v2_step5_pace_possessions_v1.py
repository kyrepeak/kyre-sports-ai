from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "cfb-game-total-page1-v2-step5-pace-possessions"
SOURCE_MAIN = "53c4bf0aa194befe56934d476f0f1a1a22d3d40d"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _reachable_clean_pages(start: int) -> set[int]:
    pending = [start]
    seen: set[int] = set()
    pattern = re.compile(r"cfb_game_total_clean_page_v(\d+)")
    while pending:
        version = pending.pop()
        if version in seen:
            continue
        path = ROOT / f"cfb_game_total_clean_page_v{version}.py"
        if not path.exists():
            continue
        seen.add(version)
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            child = int(match.group(1))
            if child not in seen and child < version:
                pending.append(child)
    return seen


def test_current_v38_route_preserves_v17_step5_owner() -> None:
    reachable = _reachable_clean_pages(38)
    assert 17 in reachable
    assert {38, 36, 35, 34, 33, 28, 17}.issubset(reachable)

    v17 = read("cfb_game_total_clean_page_v17.py")
    assert "import cfb_game_total_step5_pace_v1 as step5_owner" in v17
    assert "if int(number) == 5:" in v17
    assert "step5_owner.render_step5_html" in v17
    assert "return original_step_evidence(" in v17
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in v17
    assert "MAY_MODIFY_PROJECTION = False" in v17


def test_step4_public_repair_does_not_replace_step5_evidence_seam() -> None:
    repair = read("cfb_game_total_page1_v2_step4_public_repair_v1.py")
    assert "_game_total_hero_html" in repair
    assert "_step_evidence_html" not in repair

    v38 = read("cfb_game_total_clean_page_v38.py")
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in v38
    assert "MAY_MODIFY_PROJECTION = False" in v38


def test_step5_is_multisource_and_espn_is_last_resort_only() -> None:
    engine = read("cfb_game_total_step5_pace_v1.py")
    assert "CFB_GAME_TOTAL_STEP5_PACE_POSSESSIONS_ACTIVE" in engine
    assert "CFB_GAME_TOTAL_STEP5_NCAA_PBP_MULTISOURCE_ACTIVE" in engine
    assert "raw.githubusercontent.com/sportsdataverse/" in engine
    assert "cfbfastR-cfb-raw/main/cfb/json/final" in engine
    assert "Punt & Rally" in engine
    assert "ESPN summary is a last-resort recovery only" in engine
    assert 'row["delivery"] = "espn_summary_last_resort"' in engine
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in engine
    assert "MAY_MODIFY_PROJECTION = False" in engine
    assert 'state = "DATA LIMITED"' in engine
    assert 'state = "CHECK"' in engine
    assert 'state = "READY"' in engine


def test_step5_existing_contract_exposes_pace_and_expected_possessions() -> None:
    engine = read("cfb_game_total_step5_pace_v1.py")
    assert '"pace_index"' in engine
    assert '"expected_away_drives"' in engine
    assert '"expected_home_drives"' in engine
    assert '"expected_combined_drives"' in engine
    assert '"expected_combined_plays"' in engine
    assert '"matchup_read"' in engine
    assert '"data_confidence"' in engine
    for label in (
        "PLAYS / GAME",
        "SECONDS / PLAY",
        "SITUATION-NEUTRAL PACE",
        "DRIVES / GAME",
        "NO-HUDDLE RATE",
        "AVG DRIVE TIME",
    ):
        assert label in engine


def test_step5_control_plane_metadata_is_exact() -> None:
    execution = json.loads(
        read("devsystem/execution_plans/cfb-game-total-page1-v2-step5-pace-possessions.json")
    )
    proof = json.loads(
        read("devsystem/runless_proof_plans/cfb-game-total-page1-v2-step5-pace-possessions.json")
    )
    ledger = json.loads(
        read("devsystem/task_ledgers/cfb-game-total-page1-v2-step5-pace-possessions.json")
    )
    for payload in (execution, proof, ledger):
        assert payload["task_id"] == TASK_ID
        assert payload["source_main_sha"] == SOURCE_MAIN
    assert proof["required_check"] == "runless-final-gate"
    assert proof["required_check_app_id"] == 5204253
    assert execution["product_runtime_mutations"] == 0
    assert ledger["freeze_token"] == "CFB_GAME_TOTAL_PAGE1_V2_STEP5_PACE_POSSESSIONS_FROZEN"
