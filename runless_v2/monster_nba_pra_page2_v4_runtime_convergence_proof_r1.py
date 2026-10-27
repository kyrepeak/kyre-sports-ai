"""MONSTER-only proof for NBA PRA Page 2 V4 Streamlit runtime convergence R1.

This module is preview-only proof transport. It never consumes shared execution
leases, shared frozen-registry state, API2 receipts, checkpoints, or evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any
from urllib.parse import quote

VERSION = "MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_PROOF_R1"
AUTHORITY = "MONSTER_ONLY"
TASK_ID = "monster-nba-pra-page2-v4-runtime-convergence-r1"
WORKSTREAM = TASK_ID
PR_NUMBER = 1885
CANDIDATE_BRANCH = "monster-nba-pra-page2-v4-runtime-convergence-r1"
PROOF_BRANCH = "monster-nba-pra-page2-v4-runtime-convergence-proof-r1"
BASE_BRANCH = "main"
EXPECTED_MAIN_SHA = "7f1b99b79cefecf42bae2be7d406b8c00535f76b"
TARGET_CANDIDATE_SHA = "7f6cf3443fda1aff1f2df04fb0ef0f491a85f635"
BASE_APP_BLOB = "e4e5ff6d79d35a51f8ab93dc2bf72e6b965229a2"
TARGET_APP_BLOB = "7f0ee61f8cf3fa38d41412e724d5ca1f23b0989c"
AUTHORIZATION_ID = "AUTH-MONSTER-NBA-PRA-PAGE2-V4-RUNTIME-CONVERGENCE-R1-1885"
GATE_NAME = "runless-final-gate"
GITHUB_APP_ID = "5204253"
RECEIPT_REF = "monster-step2g-proof-receipts-v1"
RECEIPT_DIR = "devsystem/monster_step2g_runtime_convergence_proof_receipts"
PLAN_PATH = f"devsystem/runless_proof_plans/{TASK_ID}.json"
MARKER = "MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_R1_20261026"
EXPECTED_CHANGED_PATHS = frozenset({
    "app.py",
    PLAN_PATH,
    "docs/superpowers/plans/2026-10-26-monster-nba-pra-page2-v4-runtime-convergence-r1.md",
    "tests/test_monster_nba_pra_page2_v4_runtime_convergence_r1.py",
})
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_FOREIGN_RE = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.IGNORECASE)


class MonsterRuntimeConvergenceProofFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _walk(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, str):
        yield value


def _reject_foreign(value: Any) -> None:
    if any(_FOREIGN_RE.search(text) for text in _walk(value)):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_FOREIGN_EVIDENCE_FORBIDDEN")


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise MonsterRuntimeConvergenceProofFailure(f"MONSTER_RUNTIME_CONVERGENCE_{label.upper()}_INVALID")
    return text


def _decode_text(github: Any, path: str, ref: str) -> str:
    raw = github._request("GET", f"/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}")
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_CONTENT_READ_FAILED")
    try:
        return base64.b64decode(str(raw["content"])).decode("utf-8")
    except Exception as exc:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_CONTENT_DECODE_FAILED") from exc


def _expected_app(base: str) -> str:
    constant_anchor = "_BOOTSTRAP_STARTED = perf_counter()"
    if constant_anchor not in base:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_APP_CONSTANT_ANCHOR_MISSING")
    constant = f'_MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_R1 = "{MARKER}"\n'
    out = base.replace(constant_anchor, constant + constant_anchor, 1)
    render_anchor = "\n\nrecord_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)"
    if render_anchor not in out:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_APP_RENDER_ANCHOR_MISSING")
    block = (
        "\nst.markdown(\n"
        "    f'<span style=\"position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden\">"
        "{_MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_R1}</span>',\n"
        "    unsafe_allow_html=True,\n"
        ")"
    )
    return out.replace(render_anchor, block + render_anchor, 1)


def _blob_map(tree: Mapping[str, Any], paths: Sequence[str], label: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(set(str(item) for item in paths)):
        blob = str(tree.get(path) or "").strip().lower()
        if not _SHA_RE.fullmatch(blob):
            raise MonsterRuntimeConvergenceProofFailure(f"MONSTER_RUNTIME_CONVERGENCE_{label.upper()}_MISSING:{path}")
        out[path] = blob
    return out


def _receipt_path(candidate_sha: str) -> str:
    return f"{RECEIPT_DIR}/{candidate_sha}.json"


def _read_receipt(github: Any, candidate_sha: str) -> dict[str, Any] | None:
    raw = github._request(
        "GET",
        f"/contents/{quote(_receipt_path(candidate_sha), safe='/')}?ref={quote(RECEIPT_REF, safe='')}",
        allow_404=True,
    )
    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_READ_FAILED")
    try:
        value = json.loads(base64.b64decode(str(raw["content"])).decode("utf-8"))
    except Exception as exc:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_DECODE_FAILED") from exc
    return validate_receipt(value)


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_NOT_OBJECT")
    supplied = deepcopy(dict(value))
    _reject_foreign(supplied)
    digest = str(supplied.get("digest") or "").lower()
    if not _DIGEST_RE.fullmatch(digest):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_DIGEST_INVALID")
    core = dict(supplied)
    core.pop("digest", None)
    if _digest(core) != digest:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_DIGEST_MISMATCH")
    if core.get("authority") != AUTHORITY or core.get("task_id") != TASK_ID or core.get("candidate_sha") != TARGET_CANDIDATE_SHA:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_IDENTITY_MISMATCH")
    return supplied


def _write_or_read_receipt(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    existing = _read_receipt(github, TARGET_CANDIDATE_SHA)
    if existing is not None:
        if existing != dict(receipt):
            raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_COLLISION")
        return existing
    content = base64.b64encode((_canonical(receipt) + "\n").encode("utf-8")).decode("ascii")
    github._request(
        "PUT",
        f"/contents/{quote(_receipt_path(TARGET_CANDIDATE_SHA), safe='/')}",
        json={
            "message": f"MONSTER runtime convergence proof {TARGET_CANDIDATE_SHA[:12]}",
            "content": content,
            "branch": RECEIPT_REF,
        },
    )
    readback = _read_receipt(github, TARGET_CANDIDATE_SHA)
    if readback != dict(receipt):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_RECEIPT_READBACK_MISMATCH")
    return readback


def _matching_gate(check: Mapping[str, Any], digest: str) -> bool:
    output = dict(check.get("output") or {})
    return (
        check.get("name") == GATE_NAME
        and check.get("conclusion") == "success"
        and str(check.get("head_sha") or "") == TARGET_CANDIDATE_SHA
        and str((check.get("app") or {}).get("id")) == GITHUB_APP_ID
        and digest in str(output.get("summary") or "")
        and AUTHORITY in str(output.get("summary") or "")
    )


def _publish_gate_and_readback(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    digest = str(receipt["digest"])
    checks = github._request("GET", f"/commits/{TARGET_CANDIDATE_SHA}/check-runs")
    for check in list((checks or {}).get("check_runs", [])):
        if _matching_gate(check, digest):
            return dict(check)
    github._request(
        "POST",
        "/check-runs",
        json={
            "name": GATE_NAME,
            "head_sha": TARGET_CANDIDATE_SHA,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "MONSTER NBA PRA Page 2 Runtime Convergence Proof",
                "summary": f"authority={AUTHORITY} receipt={digest} task={TASK_ID}",
            },
        },
    )
    checks = github._request("GET", f"/commits/{TARGET_CANDIDATE_SHA}/check-runs")
    for check in list((checks or {}).get("check_runs", [])):
        if _matching_gate(check, digest):
            return dict(check)
    raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_GATE_READBACK_FAILED")


async def prove_runtime_convergence(*, github: Any, sandbox: Any, expected_preview_sha: str) -> dict[str, Any]:
    preview_sha = _sha(expected_preview_sha, "preview_sha")
    proof_ref = github._request("GET", f"/git/ref/heads/{quote(PROOF_BRANCH, safe='')}")
    if _sha(((proof_ref or {}).get("object") or {}).get("sha"), "proof_branch_sha") != preview_sha:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_PROOF_PREVIEW_DRIFT")
    if _sha(github.main_sha(), "current_main_sha") != EXPECTED_MAIN_SHA:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_MAIN_DRIFT")

    pr = github._request("GET", f"/pulls/{PR_NUMBER}")
    head = dict(pr.get("head") or {})
    base = dict(pr.get("base") or {})
    if str(pr.get("state") or "") != "open" or str(head.get("ref") or "") != CANDIDATE_BRANCH or str(base.get("ref") or "") != BASE_BRANCH:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_PR_IDENTITY_MISMATCH")
    if _sha(head.get("sha"), "candidate_sha") != TARGET_CANDIDATE_SHA or _sha(base.get("sha"), "pr_base_sha") != EXPECTED_MAIN_SHA:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_PR_HEAD_OR_BASE_DRIFT")

    compare = github._request("GET", f"/compare/{EXPECTED_MAIN_SHA}...{TARGET_CANDIDATE_SHA}")
    if str(compare.get("status") or "") != "ahead":
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_ANCESTRY_MISMATCH")
    changed_paths = sorted(str(item.get("filename") or "") for item in compare.get("files", []))
    if set(changed_paths) != set(EXPECTED_CHANGED_PATHS):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_CHANGED_PATH_SCOPE_VIOLATION")

    main_tree = github.tree_blobs(EXPECTED_MAIN_SHA)
    candidate_tree = github.tree_blobs(TARGET_CANDIDATE_SHA)
    if str(main_tree.get("app.py") or "").lower() != BASE_APP_BLOB or str(candidate_tree.get("app.py") or "").lower() != TARGET_APP_BLOB:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_APP_BLOB_MISMATCH")
    base_app = _decode_text(github, "app.py", EXPECTED_MAIN_SHA)
    candidate_app = _decode_text(github, "app.py", TARGET_CANDIDATE_SHA)
    if MARKER in base_app or candidate_app != _expected_app(base_app):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_APP_DELTA_INVALID")

    plan = github._content_json(PLAN_PATH, TARGET_CANDIDATE_SHA)
    if plan.get("task_id") != TASK_ID or plan.get("workstream") != WORKSTREAM or _sha(plan.get("source_main_sha"), "plan_main_sha") != EXPECTED_MAIN_SHA:
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_PLAN_IDENTITY_MISMATCH")
    tree = candidate_tree
    artifact_map = _blob_map(tree, plan.get("artifacts") or [], "artifact")
    dependency_map = _blob_map(tree, plan.get("dependencies") or [], "dependency")

    sandbox_result = await sandbox.execute(
        candidate_sha=TARGET_CANDIDATE_SHA,
        task_id=TASK_ID,
        github_token=github.installation_token(),
        timeout_seconds=int(plan.get("timeout_seconds", 600)),
    )
    if sandbox_result.candidate_sha != TARGET_CANDIDATE_SHA or sandbox_result.task_id != TASK_ID or _canonical(sandbox_result.plan) != _canonical(plan):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_SANDBOX_IDENTITY_MISMATCH")
    evidence = [item.model_dump(mode="json") for item in sandbox_result.evidence]
    if not sandbox_result.ok or not evidence or any(item.get("ok") is not True for item in evidence):
        raise MonsterRuntimeConvergenceProofFailure("MONSTER_RUNTIME_CONVERGENCE_SANDBOX_NOT_GREEN")

    core = {
        "schema_version": 1,
        "version": VERSION,
        "authority": AUTHORITY,
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": TARGET_CANDIDATE_SHA,
        "expected_main_sha": EXPECTED_MAIN_SHA,
        "pr_number": PR_NUMBER,
        "branch": CANDIDATE_BRANCH,
        "step2a": {
            "authorization_id": AUTHORIZATION_ID,
            "one_active_problem": True,
            "one_branch": CANDIDATE_BRANCH,
            "one_pr": PR_NUMBER,
        },
        "anti_loop": {"blind_retry_allowed": False, "duplicate_proof_lane_allowed": False},
        "one_use_thaw": {
            "path": "app.py",
            "from_blob": BASE_APP_BLOB,
            "to_blob": TARGET_APP_BLOB,
            "marker": MARKER,
            "shared_registry_consumed": False,
        },
        "changed_paths": changed_paths,
        "artifact_map": artifact_map,
        "dependency_map": dependency_map,
        "sandbox_evidence": evidence,
        "sandbox_evidence_digest": _digest(evidence),
        "plan_digest": _digest(plan),
        "gate_name": GATE_NAME,
        "github_app_id": GITHUB_APP_ID,
        "shared_execution_lease_consumed": False,
        "shared_frozen_state_consumed": False,
    }
    _reject_foreign(core)
    receipt = dict(core)
    receipt["digest"] = _digest(core)
    receipt = _write_or_read_receipt(github, receipt)
    gate = _publish_gate_and_readback(github, receipt)
    return {
        "state": "MERGE_AUTHORIZED",
        "authority": AUTHORITY,
        "candidate_sha": TARGET_CANDIDATE_SHA,
        "receipt_digest": receipt["digest"],
        "gate_check_run_id": int(gate["id"]),
        "github_app_id": str((gate.get("app") or {}).get("id") or ""),
        "failure_class": "NONE",
    }
