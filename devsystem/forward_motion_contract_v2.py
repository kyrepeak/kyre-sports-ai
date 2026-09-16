"""Permanent contract validator for Monster Anti-Loop V2."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devsystem.a9_anti_loop_replay_v1 import run_replay as run_v1_replay
from devsystem.action_ledger_v2 import ActionLedgerFailure, verify_pr_ledger
from devsystem.anti_loop_replay_v2 import run_replay as run_v2_replay
from devsystem.forward_motion_v2 import load_policy


class ForwardMotionV2ContractFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardMotionV2ContractFailure(message)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ForwardMotionV2ContractFailure(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _prove_bootstrap_self_expiring() -> bool:
    with tempfile.TemporaryDirectory(prefix="monster-v2-bootstrap-") as tmp:
        root = Path(tmp)
        _git(root, "init", "-b", "main")
        _git(root, "config", "user.email", "monster@example.com")
        _git(root, "config", "user.name", "Monster Contract")
        (root / "README.md").write_text("base\n", encoding="utf-8")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "base")
        base = _git(root, "rev-parse", "HEAD")

        (root / "devsystem" / "task_ledgers").mkdir(parents=True)
        policy_path = root / "devsystem" / "forward_motion_policy_v2.json"
        policy_path.write_text("{}\n", encoding="utf-8")
        ledger_path = root / "devsystem" / "task_ledgers" / "bootstrap.json"
        bootstrap = {
            "version": 2,
            "task_id": "monster-anti-loop-v2-activation",
            "activation_mode": "v2-bootstrap",
            "status": "DONE",
            "bootstrap_scope": [
                "devsystem/forward_motion_policy_v2.json",
                "devsystem/task_ledgers/bootstrap.json",
            ],
            "action_log": {
                "head_chain_hash": "BOOTSTRAP-V2-ACTIVATION",
                "events": [],
                "consumed_receipts": [],
            },
            "transition_history": [],
            "override_events": [],
        }
        ledger_path.write_text(json.dumps(bootstrap, indent=2) + "\n", encoding="utf-8")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "activate v2")
        activated = _git(root, "rev-parse", "HEAD")
        first = verify_pr_ledger(base, activated, root=root)
        _require(first.get("mode") == "v2-bootstrap", "initial V2 bootstrap was not accepted")

        bootstrap["bootstrap_reason"] = "attempted reuse after activation"
        ledger_path.write_text(json.dumps(bootstrap, indent=2) + "\n", encoding="utf-8")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "reuse bootstrap")
        reuse_head = _git(root, "rev-parse", "HEAD")
        try:
            verify_pr_ledger(activated, reuse_head, root=root)
        except ActionLedgerFailure as exc:
            _require(
                "bootstrap is invalid after V2 activation" in str(exc),
                "bootstrap reuse failed for the wrong reason",
            )
            return True
        raise ForwardMotionV2ContractFailure("bootstrap remained valid after V2 activation")


def validate() -> dict[str, Any]:
    policy = load_policy()
    _require(policy.get("mode") == "strict_auto_continue_v2", "V2 mode drift")
    budgets = policy.get("retry_budgets") or {}
    _require(int(budgets.get("deterministic-regression", -1)) == 0, "deterministic retry budget drift")
    _require(int(budgets.get("transient-capable", -1)) == 1, "transient retry budget drift")
    _require(int(budgets.get("unknown_evidence_actions", -1)) == 1, "unknown evidence budget drift")
    _require(int((policy.get("stagnation") or {}).get("max_no_progress_actions", -1)) == 3, "stagnation threshold drift")
    _require((policy.get("proof_rules") or {}).get("max_active_blockers") == 1, "blocker cardinality drift")
    override_rules = policy.get("override_rules") or {}
    _require(override_rules.get("allowed_source") == "user_explicit", "override source drift")
    _require(override_rules.get("single_use") is True, "override single-use drift")
    _require(override_rules.get("exact_action_only") is True, "override exact-action drift")
    _require(override_rules.get("cannot_disable_policy") is True, "override policy-disable drift")
    _require(override_rules.get("cryptographic_human_identity_claim") is False, "override identity claim drift")

    v2 = run_v2_replay()
    _require(v2.get("status") == "GREEN", "V2 adversarial replay failed")
    _require(v2.get("exact_duplicates_denied", 0) >= 1, "duplicate guard drift")
    _require(v2.get("semantic_root_cause_loops_denied", 0) >= 2, "semantic root-cause guard drift")
    _require(v2.get("stagnation_locks", 0) >= 1, "stagnation guard drift")
    _require(v2.get("closed_checkpoint_reopens_denied", 0) >= 1, "monotonic checkpoint guard drift")
    _require(v2.get("second_blockers_deferred", 0) >= 1, "single blocker guard drift")
    _require(v2.get("valid_single_use_overrides") == 1, "valid override path drift")
    _require(v2.get("invalid_overrides_denied", 0) >= 1, "invalid override guard drift")
    _require(v2.get("receipt_replays_denied", 0) >= 1, "receipt single-use drift")
    _require(v2.get("tamper_attempts_denied", 0) >= 1, "receipt-chain tamper guard drift")
    _require(v2.get("post_finish_decision") == "TASK_COMPLETE", "terminal task guard drift")
    _require(v2.get("invented_post_finish_checkpoints") == 0, "post-finish work was invented")

    v1 = run_v1_replay()
    _require(v1.get("status") == "GREEN", "V1 historical replay regressed")
    _require(v1.get("post_finish_decision") == "TASK_COMPLETE", "V1 terminal guard regressed")

    bootstrap_self_expiring = _prove_bootstrap_self_expiring()

    result = {
        "status": "GREEN",
        "mode": "strict_auto_continue_v2",
        "semantic_root_cause_guard": True,
        "stagnation_guard": True,
        "monotonic_checkpoint_guard": True,
        "single_use_receipts": True,
        "receipt_chain_tamper_guard": True,
        "terminal_task_authoritative": True,
        "user_override_exact_single_use": True,
        "bootstrap_self_expiring": bootstrap_self_expiring,
        "v1_replay_still_green": True,
        "v2_replay_green": True,
    }
    print("DEVSYSTEM_FORWARD_MOTION_V2_CONTRACT_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    validate()
