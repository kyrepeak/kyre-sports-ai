from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/wnba_pra_repair_v1_step9_final_cert.py"
PLAN = ROOT / "devsystem/runless_proof_plans/wnba-pra-repair-v1-step9-final-cert.json"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-repair-v1-step9-final-cert.json"


def test_repair_step9_has_future_only_public_cert_and_final_freeze_contract():
    assert CERT.exists(), "Step-9 repair cert must exist"
    source = CERT.read_text(encoding="utf-8")
    assert "def certify_source()" in source
    assert "def run_public(" in source
    assert "speed9._future_pregame_dates()" in source
    assert "speed9._prime_wnba_pra_route" in source
    assert "speed9._set_future_slate_date_segmented" in source
    assert "nav._game_button(frame).count()" in source
    assert "WNBA_PRA_REPAIR_V1_STEP9_NO_PAST_GAMES_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP9_FUTURE_SLATE_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP9_PUBLIC_PRODUCTION_GREEN" in source
    assert "PRODUCT_RUNTIME_CHANGED = False" in source
    assert "MODEL_MATH_CHANGED = False" in source
    assert "DATA_MEANING_CHANGED = False" in source
    assert PLAN.exists(), "Step-9 Runless plan must exist"
    assert LEDGER.exists(), "Step-9 ledger must exist"
