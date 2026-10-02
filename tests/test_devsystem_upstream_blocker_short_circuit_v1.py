from __future__ import annotations

import json
from pathlib import Path

from devsystem import upstream_blocker_short_circuit_v1 as gate


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "devsystem/upstream_certification_registry_v1.json"
STEP3_CERT = ROOT / "devsystem/wnba_pra_repair_v1_step3_data_completeness_cert.py"


def test_real_wnba_step2_blocks_step3_public_proof_today():
    result = gate.evaluate_upstream_dependency("wnba-pra-repair-v1-step3-public")
    assert result["status"] == "UPSTREAM_BLOCKED"
    assert result["decision"] == "UPSTREAM_BLOCKED"
    assert result["reason"] == "GREEN_PLUS_FROZEN_NOT_CLAIMED"
    assert result["downstream_proof_allowed"] is False
    assert result["expensive_proof_allowed"] is False
    assert result["product_patch_allowed"] is False


def test_green_frozen_upstream_opens_downstream_proof():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    spec = payload["dependencies"]["wnba-pra-repair-v1-step3-public"]
    ledger = {
        "task_id": "green-upstream",
        "status": "DONE",
        "green_plus_frozen_claimed": True,
    }
    result = gate.evaluate_ledger_payload(
        "wnba-pra-repair-v1-step3-public",
        spec,
        ledger,
    )
    assert result["status"] == "GREEN"
    assert result["decision"] == "PROCEED_DOWNSTREAM_PROOF"
    assert result["downstream_proof_allowed"] is True


def test_source_complete_is_not_the_same_as_green_frozen():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    spec = payload["dependencies"]["wnba-pra-repair-v1-step3-public"]
    result = gate.evaluate_ledger_payload(
        "wnba-pra-repair-v1-step3-public",
        spec,
        {"task_id": "source-only", "status": "DONE", "green_plus_frozen_claimed": False},
    )
    assert result["status"] == "UPSTREAM_BLOCKED"
    assert result["reason"] == "GREEN_PLUS_FROZEN_NOT_CLAIMED"


def test_step3_preflight_happens_before_browser_import_and_retry_loop():
    source = STEP3_CERT.read_text(encoding="utf-8")
    run = source.split("def run_production", 1)[1]
    assert run.index("upstream = upstream_preflight") < run.index("from playwright.sync_api import sync_playwright")
    assert run.index("upstream = upstream_preflight") < run.index("for attempt in range(1, DEPLOYMENT_ATTEMPTS + 1)")
    assert '"deployment_attempts_used": 0' in run
    assert '"browser_proof_attempted": False' in run


def test_contract_self_test_is_green_and_non_mutating():
    result = gate.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["real_wnba_case"] == "UPSTREAM_BLOCKED"
    assert result["blocked_proof_allowed"] is False
    assert result["green_frozen_proof_allowed"] is True
    assert result["network_calls"] is False
    assert result["product_runtime_mutation"] is False
