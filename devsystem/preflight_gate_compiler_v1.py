"""MONSTER V6 Step 2 — Preflight Gate Compiler V1.

Read-only compiler for cheap, deterministic pre-CI failures.

It combines exact-head identity, Action Ledger V2 validity, Python syntax,
required test/permanent-contract ownership, workflow shape, frozen-path
protection, scope authorization, and the existing adaptive proof plan into one
fail-closed decision.

The compiler performs no network calls and grants no mutation authority.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from devsystem.action_ledger_v2 import ActionLedgerFailure, validate_action_ledger
from devsystem.adaptive_proof_engine_v1 import plan_proof

VERSION = "MONSTER_V6_PREFLIGHT_GATE_COMPILER_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class PreflightGateFailure(RuntimeError):
    pass


def _norm_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text or text.startswith("/") or text.startswith("../") or ".." in PurePosixPath(text).parts:
        raise PreflightGateFailure("invalid repository path")
    return text


def _unique_paths(values: Sequence[Any]) -> list[str]:
    return sorted({_norm_path(v) for v in values})


def _overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _is_thawed(path: str, thawed: Sequence[str]) -> bool:
    return any(_overlap(path, thaw) for thaw in thawed)


def _workflow_shape(text: str) -> tuple[bool, list[str]]:
    value = str(text or "")
    missing = [
        marker
        for marker in ("name:", "on:", "jobs:")
        if not re.search(rf"(?m)^\s*{re.escape(marker)}", value)
    ]
    return not missing, missing


def _compile_python(path: str, source: str) -> str | None:
    try:
        compile(str(source), path, "exec")
    except SyntaxError as exc:
        location = f"{path}:{exc.lineno or 0}:{exc.offset or 0}"
        return f"{location} {exc.msg}"
    return None


def compile_preflight(
    *,
    changed_paths: Sequence[str],
    task_ledgers: Mapping[str, Mapping[str, Any]],
    python_sources: Mapping[str, str],
    available_paths: Sequence[str],
    required_test_paths: Sequence[str] = (),
    required_permanent_paths: Sequence[str] = (),
    workflow_texts: Mapping[str, str] | None = None,
    permanent_contract_text: str = "",
    required_permanent_markers: Sequence[str] = (),
    expected_head_sha: str,
    observed_head_sha: str,
    frozen_paths: Sequence[str] = (),
    thawed_paths: Sequence[str] = (),
    scope_authorized: bool,
) -> dict[str, Any]:
    changed = _unique_paths(changed_paths)
    available = set(_unique_paths(available_paths))
    required_tests = _unique_paths(required_test_paths)
    required_permanent = _unique_paths(required_permanent_paths)
    frozen = _unique_paths(frozen_paths)
    thawed = _unique_paths(thawed_paths)
    workflows = dict(workflow_texts or {})

    expected = str(expected_head_sha or "").strip().lower()
    observed = str(observed_head_sha or "").strip().lower()
    blockers: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    identity_valid = bool(_SHA40.fullmatch(expected) and _SHA40.fullmatch(observed))
    identity_match = identity_valid and expected == observed
    checks["exact_head_identity"] = identity_match
    if not identity_match:
        blockers.append({"code": "STALE_OR_INVALID_HEAD", "detail": {"expected": expected, "observed": observed}})

    checks["changed_paths_present"] = bool(changed)
    if not changed:
        blockers.append({"code": "NO_CHANGED_PATHS", "detail": {}})

    ledger_paths = [
        path for path in changed
        if path.startswith("devsystem/task_ledgers/") and path.endswith(".json")
    ]
    ledger_ok = len(ledger_paths) == 1
    ledger_detail: dict[str, Any] = {"count": len(ledger_paths), "paths": ledger_paths}
    if ledger_ok:
        ledger_path = ledger_paths[0]
        ledger = task_ledgers.get(ledger_path)
        if not isinstance(ledger, Mapping):
            ledger_ok = False
            ledger_detail["reason"] = "ledger payload missing"
        else:
            try:
                if int(ledger.get("version", 0)) != 2:
                    raise ActionLedgerFailure("task ledger version must be 2")
                if str(ledger.get("status") or "") != "DONE":
                    raise ActionLedgerFailure("task ledger status must be DONE")
                ledger_detail["validation"] = validate_action_ledger(dict(ledger))
            except (ActionLedgerFailure, ValueError, TypeError) as exc:
                ledger_ok = False
                ledger_detail["reason"] = str(exc)
    checks["action_ledger_v2"] = ledger_ok
    if not ledger_ok:
        blockers.append({"code": "ACTION_LEDGER_V2_INVALID", "detail": ledger_detail})

    syntax_errors: list[str] = []
    changed_python = [path for path in changed if path.endswith(".py")]
    for path in changed_python:
        source = python_sources.get(path)
        if source is None:
            syntax_errors.append(f"{path}: source missing")
            continue
        error = _compile_python(path, source)
        if error:
            syntax_errors.append(error)
    checks["python_syntax"] = not syntax_errors
    if syntax_errors:
        blockers.append({"code": "PYTHON_SYNTAX_INVALID", "detail": {"errors": syntax_errors}})

    missing_tests = sorted(path for path in required_tests if path not in available)
    checks["required_tests_present"] = not missing_tests
    if missing_tests:
        blockers.append({"code": "REQUIRED_TEST_MISSING", "detail": {"paths": missing_tests}})

    missing_permanent_paths = sorted(path for path in required_permanent if path not in available)
    checks["required_permanent_paths_present"] = not missing_permanent_paths
    if missing_permanent_paths:
        blockers.append({"code": "PERMANENT_CONTRACT_PATH_MISSING", "detail": {"paths": missing_permanent_paths}})

    missing_markers = sorted(
        str(marker)
        for marker in required_permanent_markers
        if str(marker) not in str(permanent_contract_text or "")
    )
    checks["permanent_contract_markers"] = not missing_markers
    if missing_markers:
        blockers.append({"code": "PERMANENT_CONTRACT_MARKER_MISSING", "detail": {"markers": missing_markers}})

    workflow_failures: dict[str, list[str]] = {}
    for path in [p for p in changed if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]:
        if path not in workflows:
            workflow_failures[path] = ["workflow text missing"]
            continue
        good, missing = _workflow_shape(workflows[path])
        if not good:
            workflow_failures[path] = missing
    checks["workflow_contract_shape"] = not workflow_failures
    if workflow_failures:
        blockers.append({"code": "WORKFLOW_CONTRACT_INVALID", "detail": workflow_failures})

    frozen_hits = sorted({
        path
        for path in changed
        for protected in frozen
        if _overlap(path, protected) and not _is_thawed(path, thawed)
    })
    checks["frozen_artifacts_protected"] = not frozen_hits
    if frozen_hits:
        blockers.append({"code": "FROZEN_ARTIFACT_TOUCH_WITHOUT_THAW", "detail": {"paths": frozen_hits}})

    checks["scope_lease_authorized"] = bool(scope_authorized)
    if not scope_authorized:
        blockers.append({"code": "SCOPE_LEASE_NOT_AUTHORIZED", "detail": {}})

    proof_plan = plan_proof(
        changed or ["__no_change__"],
        expected_head_sha=expected,
        observed_head_sha=observed,
    )
    proof_plan_ready = proof_plan.get("state") != "STALE_HEAD"
    checks["adaptive_proof_plan_ready"] = proof_plan_ready
    if not proof_plan_ready and not any(b["code"] == "STALE_OR_INVALID_HEAD" for b in blockers):
        blockers.append({"code": "ADAPTIVE_PROOF_PLAN_BLOCKED", "detail": proof_plan})

    decision = "GO_TO_CI" if not blockers else "BLOCK_BEFORE_CI"
    return {
        "version": VERSION,
        "status": "GREEN" if not blockers else "BLOCKED",
        "decision": decision,
        "changed_paths": changed,
        "checks": checks,
        "blockers": blockers,
        "proof_plan": proof_plan,
        "avoided_failure_classes": [
            "STALE_HEAD",
            "ACTION_LEDGER_V2",
            "PYTHON_SYNTAX",
            "MISSING_TEST",
            "PERMANENT_CONTRACT",
            "WORKFLOW_SHAPE",
            "FROZEN_ARTIFACT",
            "SCOPE_LEASE",
        ],
        "next_legal_action": "START_AUTHORITATIVE_CI" if not blockers else "PATCH_PREFLIGHT_BLOCKERS_ONCE",
        "protections": {
            "fail_closed": True,
            "step_2a_still_required": True,
            "scope_lease_still_required_for_mutation": True,
            "compiler_does_not_replace_terminal_proof": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        },
    }



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
        raise PreflightGateFailure(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _json_at(root: Path, ref: str, path: str) -> dict[str, Any]:
    raw = _git(root, "show", f"{ref}:{path}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PreflightGateFailure(f"invalid JSON at {ref}:{path}") from exc
    if not isinstance(value, dict):
        raise PreflightGateFailure(f"JSON object required at {ref}:{path}")
    return value


def _live_scope_holders(scope_state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    now = datetime.now(timezone.utc)
    live: list[Mapping[str, Any]] = []
    for holder in scope_state.get("holders") or []:
        try:
            expires = datetime.fromisoformat(str(holder.get("expires_at_utc") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now < expires.astimezone(timezone.utc):
            live.append(holder)
    return live


def _scope_authorized_for_branch(
    scope_state: Mapping[str, Any],
    *,
    branch: str,
    changed_paths: Sequence[str],
) -> tuple[bool, dict[str, Any]]:
    branch_token = f"branch:{str(branch or '').strip()}".lower()
    live = _live_scope_holders(scope_state)
    branch_holders = [
        holder
        for holder in live
        if branch_token in [str(v).strip().lower() for v in (holder.get("scope") or {}).get("shared_resources") or []]
    ]
    owners = {str(holder.get("owner_id") or "") for holder in branch_holders if str(holder.get("owner_id") or "")}
    owner_holders = [holder for holder in live if str(holder.get("owner_id") or "") in owners]
    uncovered: list[str] = []
    for path in changed_paths:
        covered = False
        for holder in owner_holders:
            for write_path in (holder.get("scope") or {}).get("write_paths") or []:
                write = _norm_path(write_path)
                if path == write or path.startswith(write + "/"):
                    covered = True
                    break
            if covered:
                break
        if not covered:
            uncovered.append(path)
    return bool(branch_holders) and not uncovered, {
        "branch_token": branch_token,
        "owners": sorted(owners),
        "live_holder_count": len(live),
        "matching_holder_count": len(owner_holders),
        "uncovered_paths": sorted(uncovered),
    }


def compile_repository_preflight(
    *,
    root: str | Path = ".",
    base: str,
    head: str,
    branch: str,
    registry_ref: str = "refs/remotes/origin/monster-frozen-artifact-registry",
    scope_ref: str = "refs/remotes/origin/monster-scope-aware-execution-leases",
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    observed_head = _git(repo_root, "rev-parse", head).lower()
    expected_head = observed_head
    changed = [
        line.strip()
        for line in _git(repo_root, "diff", "--name-only", base, head).splitlines()
        if line.strip()
    ]
    available = [
        line.strip()
        for line in _git(repo_root, "ls-tree", "-r", "--name-only", head).splitlines()
        if line.strip()
    ]
    ledger_paths = [
        path for path in changed
        if path.startswith("devsystem/task_ledgers/") and path.endswith(".json")
    ]
    task_ledgers: dict[str, Mapping[str, Any]] = {}
    ledger: dict[str, Any] = {}
    if len(ledger_paths) == 1:
        ledger = _json_at(repo_root, head, ledger_paths[0])
        task_ledgers[ledger_paths[0]] = ledger

    python_sources = {
        path: _git(repo_root, "show", f"{head}:{path}")
        for path in changed
        if path.endswith(".py")
    }
    workflow_texts = {
        path: _git(repo_root, "show", f"{head}:{path}")
        for path in changed
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    }

    regression = ledger.get("regression_debt") if isinstance(ledger, Mapping) else {}
    regression = regression if isinstance(regression, Mapping) else {}
    required_tests = [
        str(regression.get("permanent_test") or "").strip()
    ] if str(regression.get("permanent_test") or "").strip() else []
    required_permanent = [
        str(regression.get("permanent_contract") or "").strip()
    ] if str(regression.get("permanent_contract") or "").strip() else []

    registry = _json_at(
        repo_root,
        registry_ref,
        "devsystem/frozen_artifact_registry_state_v1.json",
    )
    frozen_paths = sorted({
        str(path)
        for entry in (registry.get("entries") or {}).values()
        for path in (entry.get("artifacts") or {})
    })
    thawed_paths = sorted({
        str(path)
        for grant in (registry.get("active_thaws") or [])
        if str(grant.get("target_head_sha") or "").lower() == observed_head
        for path in (grant.get("files") or {})
    })

    scope_state = _json_at(
        repo_root,
        scope_ref,
        "devsystem/scope_aware_execution_lease_state_v1.json",
    )
    scope_ok, scope_detail = _scope_authorized_for_branch(
        scope_state,
        branch=branch,
        changed_paths=changed,
    )

    result = compile_preflight(
        changed_paths=changed,
        task_ledgers=task_ledgers,
        python_sources=python_sources,
        available_paths=available,
        required_test_paths=required_tests,
        required_permanent_paths=required_permanent,
        workflow_texts=workflow_texts,
        expected_head_sha=expected_head,
        observed_head_sha=observed_head,
        frozen_paths=frozen_paths,
        thawed_paths=thawed_paths,
        scope_authorized=scope_ok,
    )
    result["repository_preflight"] = {
        "base": _git(repo_root, "rev-parse", base).lower(),
        "head": observed_head,
        "branch": branch,
        "ledger_paths": ledger_paths,
        "registry_revision": registry.get("revision"),
        "registry_state_hash": registry.get("state_hash"),
        "scope_revision": scope_state.get("revision"),
        "scope_state_hash": scope_state.get("state_hash"),
        "scope_detail": scope_detail,
    }
    return result

def contract_self_test() -> dict[str, Any]:
    head = "a" * 40
    ledger_path = "devsystem/task_ledgers/test-preflight.json"
    ledger = {
        "version": 2,
        "task_id": "test-preflight",
        "status": "DONE",
        "action_log": {
            "head_chain_hash": "0" * 64,
            "events": [],
            "consumed_receipts": [],
        },
    }
    py_path = "devsystem/new_feature.py"
    test_path = "tests/test_new_feature.py"
    workflow_path = ".github/workflows/new-feature.yml"
    workflow = "name: New Feature\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
    good = compile_preflight(
        changed_paths=[py_path, test_path, workflow_path, ledger_path],
        task_ledgers={ledger_path: ledger},
        python_sources={py_path: "VALUE = 1\n", test_path: "def test_ok():\n    assert True\n"},
        available_paths=[py_path, test_path, workflow_path, ledger_path],
        required_test_paths=[test_path],
        workflow_texts={workflow_path: workflow},
        permanent_contract_text="new_feature.py test_new_feature.py",
        required_permanent_markers=["new_feature.py", "test_new_feature.py"],
        expected_head_sha=head,
        observed_head_sha=head,
        frozen_paths=["devsystem/frozen.py"],
        scope_authorized=True,
    )
    stale = compile_preflight(
        changed_paths=[py_path, ledger_path],
        task_ledgers={ledger_path: ledger},
        python_sources={py_path: "VALUE = 1\n"},
        available_paths=[py_path, ledger_path],
        expected_head_sha=head,
        observed_head_sha="b" * 40,
        scope_authorized=True,
    )
    bad_ledger = compile_preflight(
        changed_paths=[py_path, ledger_path],
        task_ledgers={ledger_path: {**ledger, "status": "OPEN"}},
        python_sources={py_path: "VALUE = 1\n"},
        available_paths=[py_path, ledger_path],
        expected_head_sha=head,
        observed_head_sha=head,
        scope_authorized=True,
    )
    bad_syntax = compile_preflight(
        changed_paths=[py_path, ledger_path],
        task_ledgers={ledger_path: ledger},
        python_sources={py_path: "def broken(:\n    pass\n"},
        available_paths=[py_path, ledger_path],
        expected_head_sha=head,
        observed_head_sha=head,
        scope_authorized=True,
    )
    frozen = compile_preflight(
        changed_paths=["devsystem/frozen.py", ledger_path],
        task_ledgers={ledger_path: ledger},
        python_sources={"devsystem/frozen.py": "VALUE = 1\n"},
        available_paths=["devsystem/frozen.py", ledger_path],
        expected_head_sha=head,
        observed_head_sha=head,
        frozen_paths=["devsystem/frozen.py"],
        scope_authorized=True,
    )
    no_scope = compile_preflight(
        changed_paths=[py_path, ledger_path],
        task_ledgers={ledger_path: ledger},
        python_sources={py_path: "VALUE = 1\n"},
        available_paths=[py_path, ledger_path],
        expected_head_sha=head,
        observed_head_sha=head,
        scope_authorized=False,
    )
    missing_test = compile_preflight(
        changed_paths=[py_path, ledger_path],
        task_ledgers={ledger_path: ledger},
        python_sources={py_path: "VALUE = 1\n"},
        available_paths=[py_path, ledger_path],
        required_test_paths=[test_path],
        expected_head_sha=head,
        observed_head_sha=head,
        scope_authorized=True,
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "clean_bundle_goes_to_ci": good["decision"] == "GO_TO_CI",
        "stale_head_blocked_before_ci": stale["decision"] == "BLOCK_BEFORE_CI",
        "bad_ledger_blocked_before_ci": any(b["code"] == "ACTION_LEDGER_V2_INVALID" for b in bad_ledger["blockers"]),
        "syntax_error_blocked_before_ci": any(b["code"] == "PYTHON_SYNTAX_INVALID" for b in bad_syntax["blockers"]),
        "frozen_touch_blocked_before_ci": any(b["code"] == "FROZEN_ARTIFACT_TOUCH_WITHOUT_THAW" for b in frozen["blockers"]),
        "missing_scope_blocked_before_ci": any(b["code"] == "SCOPE_LEASE_NOT_AUTHORIZED" for b in no_scope["blockers"]),
        "missing_test_blocked_before_ci": any(b["code"] == "REQUIRED_TEST_MISSING" for b in missing_test["blockers"]),
        "no_mutation_authority": good["protections"]["mutation_authority_granted"] is False,
        "terminal_proof_still_required": good["protections"]["compiler_does_not_replace_terminal_proof"] is True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        "clean_bundle_goes_to_ci",
        "stale_head_blocked_before_ci",
        "bad_ledger_blocked_before_ci",
        "syntax_error_blocked_before_ci",
        "frozen_touch_blocked_before_ci",
        "missing_scope_blocked_before_ci",
        "missing_test_blocked_before_ci",
        "no_mutation_authority",
        "terminal_proof_still_required",
    ]
    if not all(result[key] is True for key in required):
        raise PreflightGateFailure("preflight gate compiler self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"]:
        raise PreflightGateFailure("preflight read-only safety invariant failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="MONSTER V6 preflight gate compiler")
    parser.add_argument("--git-preflight", action="store_true")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--branch", default="")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    if args.git_preflight:
        if not args.branch:
            raise PreflightGateFailure("--branch is required for --git-preflight")
        result = compile_repository_preflight(
            root=args.root,
            base=args.base,
            head=args.head,
            branch=args.branch,
        )
        print("MONSTER_V6_PREFLIGHT_GATE_GO" if result["decision"] == "GO_TO_CI" else "MONSTER_V6_PREFLIGHT_GATE_BLOCKED")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["decision"] == "GO_TO_CI" else 1
    print("MONSTER_V6_PREFLIGHT_GATE_COMPILER_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreflightGateFailure as exc:
        print(f"MONSTER_V6_PREFLIGHT_GATE_COMPILER_BLOCKED: {exc}")
        raise SystemExit(1)
