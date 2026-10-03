"""Registry Race Repair V1 Step 3 — WAIT + One Resume.

Final integration contract for the frozen-registry race repair.

A legitimate inherited thaw that is already merged into authoritative main but
has not yet been forward-ported into the external frozen registry becomes a
WAIT state instead of a hard failure. The proof may resume exactly once, and
only after the authoritative registry state hash changes.

This module is read-only. It never fetches, sleeps, writes Git, mutates the
registry, dispatches workflows, or grants mutation authority. The workflow
owns the bounded state watcher; this module owns classification and the
single-resume safety contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.descendant_thaw_awareness_v1 import (
    VERSION as STEP2_VERSION,
    evaluate_descendant_authority,
    plan_git_head_descendant_authority,
)
from devsystem.registry_reconciliation_barrier_v1 import VERSION as STEP1_VERSION

VERSION = "MONSTER_REGISTRY_RACE_V1_STEP3_WAIT_ONE_RESUME_V1"
EXPECTED_STEP1_VERSION = "MONSTER_REGISTRY_RACE_V1_STEP1_RECONCILIATION_BARRIER_V1"
EXPECTED_STEP2_VERSION = "MONSTER_REGISTRY_RACE_V1_STEP2_DESCENDANT_THAW_AWARENESS_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
BLIND_RETRY_ALLOWED = False
MAX_RESUMES = 1

_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class RegistryWaitResumeFailure(RuntimeError):
    pass


def _parents_green() -> None:
    if STEP1_VERSION != EXPECTED_STEP1_VERSION:
        raise RegistryWaitResumeFailure("frozen Step-1 parent version drift")
    if STEP2_VERSION != EXPECTED_STEP2_VERSION:
        raise RegistryWaitResumeFailure("frozen Step-2 parent version drift")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _token(value: Any) -> str:
    return "REGWAIT-" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:32].upper()


def _state_hash(registry: Mapping[str, Any]) -> str:
    value = str(registry.get("state_hash") or "").lower()
    if not _SHA64.fullmatch(value):
        raise RegistryWaitResumeFailure("registry state hash invalid")
    return value


def classify_from_descendant_result(
    registry: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Map Step-2 lineage truth into READY / WAIT / BLOCKED gate state."""
    _parents_green()
    state_hash = _state_hash(registry)
    decision = str(result.get("decision") or "")
    status = str(result.get("status") or "")

    if status == "BLOCKED":
        return {
            "version": VERSION,
            "status": "BLOCKED",
            "disposition": "FAIL",
            "decision": "REGISTRY_AUTHORITY_BLOCKED",
            "hard_failure": True,
            "allow_frozen_verification": False,
            "retry_allowed_now": False,
            "resume_allowed": False,
            "resume_count": 0,
            "max_resumes": MAX_RESUMES,
            "registry_state_hash": state_hash,
            "lineage_token": str(result.get("lineage_token") or ""),
            "blocked_reason": result.get("blocked"),
            "next_legal_action": "PATCH_OR_RECONCILE_AUTHORITY",
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
            "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        }

    if decision == "AUTHORIZED_INHERITED_THAW":
        basis = {
            "registry_state_hash": state_hash,
            "lineage_token": str(result.get("lineage_token") or ""),
            "candidate_head_sha": str(result.get("candidate_head_sha") or ""),
            "current_main_sha": str(result.get("current_main_sha") or ""),
            "inherited_authority_count": int(result.get("inherited_authority_count") or 0),
        }
        return {
            "version": VERSION,
            "status": "WAIT",
            "disposition": "WAIT",
            "decision": "WAIT_REGISTRY_RECONCILIATION",
            "hard_failure": False,
            "allow_frozen_verification": False,
            "retry_allowed_now": False,
            "resume_allowed": True,
            "resume_count": 0,
            "max_resumes": MAX_RESUMES,
            "registry_state_hash": state_hash,
            "lineage_token": str(result.get("lineage_token") or ""),
            "wait_state_token": _token(basis),
            "resume_trigger": "AUTHORITATIVE_REGISTRY_STATE_HASH_CHANGED",
            "next_legal_action": "WAIT_FOR_REGISTRY_STATE_CHANGE",
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
            "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        }

    if status != "GREEN":
        raise RegistryWaitResumeFailure("unexpected descendant authority status")

    return {
        "version": VERSION,
        "status": "GREEN",
        "disposition": "READY",
        "decision": "REGISTRY_VERIFICATION_READY",
        "hard_failure": False,
        "allow_frozen_verification": True,
        "retry_allowed_now": False,
        "resume_allowed": False,
        "resume_count": 0,
        "max_resumes": MAX_RESUMES,
        "registry_state_hash": state_hash,
        "lineage_token": str(result.get("lineage_token") or ""),
        "next_legal_action": "RUN_FROZEN_REGISTRY_VERIFICATION",
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "blind_retry_allowed": BLIND_RETRY_ALLOWED,
    }


def evaluate_gate(
    registry: Mapping[str, Any],
    actual_blobs: Mapping[str, str | None],
    *,
    candidate_head_sha: str,
    current_main_sha: str,
    main_descends_from_targets: Mapping[str, bool],
    candidate_descends_from_main: bool,
) -> dict[str, Any]:
    result = evaluate_descendant_authority(
        registry,
        actual_blobs,
        candidate_head_sha=candidate_head_sha,
        current_main_sha=current_main_sha,
        main_descends_from_targets=main_descends_from_targets,
        candidate_descends_from_main=candidate_descends_from_main,
    )
    return classify_from_descendant_result(registry, result)


def resume_once_from_descendant_result(
    previous_wait: Mapping[str, Any],
    current_registry: Mapping[str, Any],
    current_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Consume the one legal resume after authoritative registry progress."""
    _parents_green()
    if previous_wait.get("version") != VERSION:
        raise RegistryWaitResumeFailure("previous WAIT version drift")
    if previous_wait.get("disposition") != "WAIT":
        raise RegistryWaitResumeFailure("resume requires prior WAIT disposition")
    if previous_wait.get("decision") != "WAIT_REGISTRY_RECONCILIATION":
        raise RegistryWaitResumeFailure("resume requires registry WAIT decision")
    if previous_wait.get("resume_allowed") is not True:
        raise RegistryWaitResumeFailure("previous WAIT does not allow resume")
    if int(previous_wait.get("resume_count") or 0) != 0:
        raise RegistryWaitResumeFailure("resume budget already consumed")

    previous_hash = str(previous_wait.get("registry_state_hash") or "").lower()
    current_hash = _state_hash(current_registry)
    if previous_hash == current_hash:
        return {
            "version": VERSION,
            "status": "WAIT",
            "disposition": "WAIT",
            "decision": "REGISTRY_STATE_UNCHANGED",
            "hard_failure": False,
            "allow_frozen_verification": False,
            "retry_allowed_now": False,
            "resume_allowed": True,
            "resume_count": 0,
            "max_resumes": MAX_RESUMES,
            "registry_state_hash": current_hash,
            "previous_registry_state_hash": previous_hash,
            "wait_state_token": str(previous_wait.get("wait_state_token") or ""),
            "resume_trigger": "AUTHORITATIVE_REGISTRY_STATE_HASH_CHANGED",
            "next_legal_action": "KEEP_WAITING_WITHOUT_PROOF_RERUN",
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
            "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        }

    current_gate = classify_from_descendant_result(current_registry, current_result)
    if current_gate["status"] == "GREEN":
        return {
            **current_gate,
            "decision": "RESUMED_ONCE_REGISTRY_READY",
            "resume_count": 1,
            "resume_allowed": False,
            "retry_allowed_now": True,
            "previous_registry_state_hash": previous_hash,
            "registry_state_hash": current_hash,
            "next_legal_action": "RUN_FROZEN_REGISTRY_VERIFICATION_ONCE",
        }

    if current_gate["status"] == "WAIT":
        return {
            **current_gate,
            "status": "BLOCKED",
            "disposition": "FAIL",
            "decision": "RESUME_BUDGET_EXHAUSTED_STILL_WAITING",
            "hard_failure": True,
            "resume_count": 1,
            "resume_allowed": False,
            "retry_allowed_now": False,
            "previous_registry_state_hash": previous_hash,
            "registry_state_hash": current_hash,
            "next_legal_action": "STOP_AND_RECONCILE_REGISTRY",
        }

    return {
        **current_gate,
        "decision": "RESUMED_ONCE_AUTHORITY_BLOCKED",
        "resume_count": 1,
        "resume_allowed": False,
        "retry_allowed_now": False,
        "previous_registry_state_hash": previous_hash,
        "registry_state_hash": current_hash,
    }


def plan_git_head_gate(
    registry: Mapping[str, Any],
    *,
    candidate_head: str = "HEAD",
    current_main_sha: str,
) -> dict[str, Any]:
    result = plan_git_head_descendant_authority(
        registry,
        candidate_head=candidate_head,
        current_main_sha=current_main_sha,
    )
    return classify_from_descendant_result(registry, result)


def plan_git_head_resume_once(
    previous_wait: Mapping[str, Any],
    current_registry: Mapping[str, Any],
    *,
    candidate_head: str = "HEAD",
    current_main_sha: str,
) -> dict[str, Any]:
    result = plan_git_head_descendant_authority(
        current_registry,
        candidate_head=candidate_head,
        current_main_sha=current_main_sha,
    )
    return resume_once_from_descendant_result(previous_wait, current_registry, result)


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str | None, payload: Mapping[str, Any]) -> None:
    if path:
        Path(path).write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _sample_wait() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from devsystem.descendant_thaw_awareness_v1 import _sample_registry

    registry = _sample_registry()
    actual = {"shared.py": "b" * 40, "keep.py": "c" * 40}
    authority = evaluate_descendant_authority(
        registry,
        actual,
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    wait = classify_from_descendant_result(registry, authority)

    advanced = json.loads(json.dumps(registry))
    advanced["revision"] += 1
    advanced["source_main_sha"] = "3" * 40
    advanced["entries"]["STEP_A"]["artifacts"]["shared.py"] = "b" * 40
    advanced["active_thaws"] = []
    from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash
    advanced["state_hash"] = _hash(_payload_without_hash(advanced))

    aligned_authority = evaluate_descendant_authority(
        advanced,
        actual,
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={},
        candidate_descends_from_main=True,
    )
    return wait, advanced, aligned_authority


def self_test() -> dict[str, Any]:
    _parents_green()
    wait, advanced, aligned_authority = _sample_wait()

    if wait["status"] != "WAIT" or wait["hard_failure"] is not False:
        raise RegistryWaitResumeFailure("legitimate inherited thaw did not WAIT")
    if wait["blind_retry_allowed"] is not False:
        raise RegistryWaitResumeFailure("WAIT allowed blind retry")

    unchanged_registry = json.loads(json.dumps(advanced))
    unchanged_registry["state_hash"] = wait["registry_state_hash"]
    unchanged = resume_once_from_descendant_result(
        wait,
        unchanged_registry,
        aligned_authority,
    )
    if unchanged["decision"] != "REGISTRY_STATE_UNCHANGED":
        raise RegistryWaitResumeFailure("unchanged state did not keep WAIT")
    if unchanged["resume_count"] != 0:
        raise RegistryWaitResumeFailure("unchanged state consumed resume")

    resumed = resume_once_from_descendant_result(wait, advanced, aligned_authority)
    if resumed["decision"] != "RESUMED_ONCE_REGISTRY_READY":
        raise RegistryWaitResumeFailure("advanced registry did not resume")
    if resumed["resume_count"] != 1 or resumed["resume_allowed"] is not False:
        raise RegistryWaitResumeFailure("resume budget did not close")
    if resumed["allow_frozen_verification"] is not True:
        raise RegistryWaitResumeFailure("resumed GREEN did not permit verification")

    repeated = dict(wait)
    repeated["resume_count"] = 1
    repeated_blocked = False
    try:
        resume_once_from_descendant_result(repeated, advanced, aligned_authority)
    except RegistryWaitResumeFailure:
        repeated_blocked = True
    if not repeated_blocked:
        raise RegistryWaitResumeFailure("second resume was not blocked")

    return {
        "status": "GREEN",
        "version": VERSION,
        "legitimate_inherited_thaw_waits": wait["status"] == "WAIT",
        "wait_is_not_hard_failure": wait["hard_failure"] is False,
        "unchanged_registry_does_not_rerun_proof": (
            unchanged["decision"] == "REGISTRY_STATE_UNCHANGED"
            and unchanged["resume_count"] == 0
        ),
        "registry_hash_change_allows_one_resume": (
            resumed["decision"] == "RESUMED_ONCE_REGISTRY_READY"
            and resumed["resume_count"] == 1
        ),
        "one_resume_allows_frozen_verification": (
            resumed["allow_frozen_verification"] is True
        ),
        "second_resume_blocked": repeated_blocked,
        "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")

    evaluate = sub.add_parser("evaluate-git-head")
    evaluate.add_argument("--registry-file", required=True)
    evaluate.add_argument("--candidate-head", default="HEAD")
    evaluate.add_argument("--current-main-sha", required=True)
    evaluate.add_argument("--json-out")

    resume = sub.add_parser("resume-git-head")
    resume.add_argument("--previous-wait-file", required=True)
    resume.add_argument("--registry-file", required=True)
    resume.add_argument("--candidate-head", default="HEAD")
    resume.add_argument("--current-main-sha", required=True)
    resume.add_argument("--json-out")

    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        result = self_test()
        print("MONSTER_REGISTRY_RACE_V1_STEP3_WAIT_ONE_RESUME_GREEN")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "evaluate-git-head":
        result = plan_git_head_gate(
            _load(args.registry_file),
            candidate_head=args.candidate_head,
            current_main_sha=args.current_main_sha,
        )
    elif args.command == "resume-git-head":
        result = plan_git_head_resume_once(
            _load(args.previous_wait_file),
            _load(args.registry_file),
            candidate_head=args.candidate_head,
            current_main_sha=args.current_main_sha,
        )
    else:
        raise RegistryWaitResumeFailure("unsupported command")

    _write(args.json_out, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "GREEN":
        return 0
    if result["status"] == "WAIT":
        return 3
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RegistryWaitResumeFailure as exc:
        print("MONSTER_REGISTRY_RACE_V1_STEP3_BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
