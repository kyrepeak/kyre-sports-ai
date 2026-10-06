from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/wnba_pra_repair_v1_step9_final_production_cert.py"
PLAN = ROOT / "devsystem/runless_proof_plans/wnba-pra-repair-v1-step9-final-production-cert.json"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-repair-v1-step9-final-production-cert.json"


def test_step9_requires_ui_openable_future_identity_before_frozen_speed9():
    source = CERT.read_text(encoding="utf-8")
    assert "def _ui_openable_future_dates() -> tuple[str, ...]:" in source
    assert 'verification.get("playable_pregame") is not True' in source
    assert 'verification.get("game_id_valid") is not True' in source
    assert "game_id.isdigit()" in source
    assert 'away.get("official_team_id")' in source
    assert 'home.get("official_team_id")' in source
    assert "away_id == home_id" in source
    assert "if game_start <= now_utc:" in source
    assert "WNBA_PRA_REPAIR_V1_STEP9_UI_OPENABLE_FUTURE_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP9_NO_PAST_GAMES_GREEN" in source


def test_step9_wraps_and_restores_frozen_speed9_without_product_mutation():
    source = CERT.read_text(encoding="utf-8")
    assert "frozen_speed9._future_pregame_dates = _ui_openable_future_dates" in source
    assert "frozen_speed9._future_pregame_dates = original_future_dates" in source
    assert "frozen_speed9.run(" in source
    assert '"product_runtime_changed_by_repair_step9": False' in source
    assert '"frozen_speed_v3_step9_modified": False' in source
    assert '"past_games_allowed": False' in source
    assert "WNBA_PRA_REPAIR_V1_STEP9_PUBLIC_PRODUCTION_GREEN" in source


def test_step9_runless_plan_has_exact_new_file_scope_and_freeze_token():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["freeze_token"] == "WNBA_PRA_REPAIR_V1_STEP9_FROZEN"
    assert plan["artifacts"] == [
        "devsystem/wnba_pra_repair_v1_step9_final_production_cert.py",
        "devsystem/runless_proof_plans/wnba-pra-repair-v1-step9-final-production-cert.json",
        "devsystem/task_ledgers/wnba-pra-repair-v1-step9-final-production-cert.json",
        "tests/test_wnba_pra_repair_v1_step9.py",
    ]
    assert plan["commands"] == [
        "python -m pytest -q tests/test_wnba_pra_repair_v1_step9.py",
        "python -m devsystem.wnba_pra_repair_v1_step9_final_production_cert --source-only",
    ]


def test_step9_ledger_is_final_future_only_and_step2a_locked():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Repair V1"
    assert ledger["step"] == 9
    assert ledger["total_steps"] == 9
    assert ledger["past_games_allowed"] is False
    assert ledger["frozen_speed_v3_step9_modified"] is False
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["two_a"]["one_active_problem"] is True
