from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "devsystem" / "forward_motion_policy_v2.json"


def test_v2_policy_has_exact_retry_and_stagnation_budgets():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["mode"] == "strict_auto_continue_v2"
    assert payload["retry_budgets"] == {
        "deterministic-regression": 0,
        "transient-capable": 1,
        "unknown_evidence_actions": 1,
    }
    assert payload["stagnation"]["max_no_progress_actions"] == 3
    assert payload["proof_rules"]["max_active_blockers"] == 1
    assert payload["proof_rules"]["terminal_task_is_authoritative"] is True


def test_v2_policy_override_is_single_use_user_explicit_only():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["override_rules"] == {
        "allowed_source": "user_explicit",
        "single_use": True,
        "exact_action_only": True,
        "cannot_disable_policy": True,
        "cryptographic_human_identity_claim": False,
    }


def test_v2_bootstrap_self_expires_after_activation():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["bootstrap_rules"]["allowed_only_when_base_lacks_v2_policy"] is True
    assert payload["bootstrap_rules"]["single_activation"] is True
