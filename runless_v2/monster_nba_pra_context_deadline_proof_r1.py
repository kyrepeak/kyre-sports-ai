"""Isolated MONSTER proof publisher for NBA PRA Page 1/2 context deadline R1.

This publisher is deliberately independent from shared proof state. GitHub App
5204253 and Vercel Sandbox are transport only. Evidence, receipts, and gate
readback are MONSTER-only and any foreign-system token is rejected.
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

VERSION = "MONSTER_NBA_PRA_CONTEXT_DEADLINE_PROOF_R1"
AUTHORITY = "MONSTER_ONLY"
TASK_ID = "monster-nba-pra-context-deadline-r1"
WORKSTREAM = TASK_ID
PR_NUMBER = 1877
BRANCH = "monster-nba-pra-context-deadline-r1"
BASE_BRANCH = "main"
EXPECTED_MAIN_SHA = "0fce8407d027651224665e413c42aa556565b3ae"
AUTHORIZATION_ID = "AUTH-MONSTER-NBA-PRA-CONTEXT-DEADLINE-R1"
GATE_NAME = "runless-final-gate"
GITHUB_APP_ID = "5204253"
RECEIPT_REF = "monster-step2g-proof-receipts-v1"
RECEIPT_DIR = "devsystem/monster_step2g_proof_receipts"
PLAN_PATH = f"devsystem/runless_proof_plans/{TASK_ID}.json"

ALLOWED_CHANGED_PATHS = frozenset(
    {
        "devsystem/runless_proof_plans/monster-nba-pra-context-deadline-r1.json",
        "nba_pra_page2_api_only_v1.py",
        "nba_pra_player_context_api_v1.py",
        "runless_v2/__init__.py",
        "runless_v2/monster_nba_pra_context_deadline_proof_r1.py",
        "sports_api/api/nba_gateway_v1.py",
        "sports_api/api/nba_pra_player_context_history_v1.py",
        "sports_api/api/nba_pra_usage_v1.py",
        "tests/test_monster_nba_pra_context_deadline_proof_r1.py",
        "tests/test_monster_nba_pra_context_deadline_r1.py",
    }
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_FOREIGN_RE = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.IGNORECASE)


class MonsterNbaPraProofFailure(RuntimeError):
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
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_FOREIGN_SYSTEM_EVIDENCE_FORBIDDEN")


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise MonsterNbaPraProofFailure(f"MONSTER_NBA_PRA_PROOF_{label.upper()}_INVALID")
    return text


def _blob_map(tree: Mapping[str, Any], paths: Sequence[str], label: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(set(str(item) for item in paths)):
        blob = str(tree.get(path) or "").strip().lower()
        if not _SHA_RE.fullmatch(blob):
            raise MonsterNbaPraProofFailure(f"MONSTER_NBA_PRA_PROOF_{label.upper()}_MISSING:{path}")
        out[path] = blob
    return out


def build_receipt(
    *,
    candidate_sha: str,
    expected_main_sha: str,
    changed_paths: Sequence[str],
    artifact_map: Mapping[str, str],
    dependency_map: Mapping[str, str],
    evidence: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    candidate = _sha(candidate_sha, "candidate_sha")
    main_sha = _sha(expected_main_sha, "expected_main_sha")
    paths = sorted(set(str(path) for path in changed_paths))
    if not paths or not set(paths).issubset(ALLOWED_CHANGED_PATHS):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_CHANGED_PATH_SCOPE_VIOLATION")
    if candidate == main_sha:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_CANDIDATE_MUST_DIFFER_FROM_MAIN")
    if plan.get("task_id") != TASK_ID or plan.get("workstream") != WORKSTREAM:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PLAN_IDENTITY_MISMATCH")
    if str(plan.get("source_main_sha") or "").lower() != main_sha:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PLAN_MAIN_IDENTITY_MISMATCH")
    normalized_evidence = [deepcopy(dict(item)) for item in evidence]
    if not normalized_evidence or any(item.get("ok") is not True for item in normalized_evidence):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_SANDBOX_EVIDENCE_NOT_GREEN")
    core = {
        "schema_version": 1,
        "version": VERSION,
        "authority": AUTHORITY,
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": candidate,
        "expected_main_sha": main_sha,
        "pr_number": PR_NUMBER,
        "branch": BRANCH,
        "base_branch": BASE_BRANCH,
        "step2a": {
            "authorization_id": AUTHORIZATION_ID,
            "one_use_scope": True,
            "one_active_problem": True,
            "one_branch": BRANCH,
            "one_pr": PR_NUMBER,
        },
        "anti_loop": {"duplicate_proof_lane_allowed": False, "blind_retry_allowed": False},
        "changed_paths": paths,
        "artifact_map": dict(sorted((str(k), str(v).lower()) for k, v in artifact_map.items())),
        "dependency_map": dict(sorted((str(k), str(v).lower()) for k, v in dependency_map.items())),
        "sandbox_evidence": normalized_evidence,
        "sandbox_evidence_digest": _digest(normalized_evidence),
        "plan_digest": _digest(plan),
        "gate_name": GATE_NAME,
        "github_app_id": GITHUB_APP_ID,
    }
    _reject_foreign(core)
    receipt = dict(core)
    receipt["digest"] = _digest(core)
    return receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_NOT_OBJECT")
    supplied = deepcopy(dict(value))
    _reject_foreign(supplied)
    digest = str(supplied.get("digest") or "").lower()
    if not _DIGEST_RE.fullmatch(digest):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_DIGEST_INVALID")
    core = dict(supplied)
    core.pop("digest", None)
    if _digest(core) != digest:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_DIGEST_MISMATCH")
    if core.get("version") != VERSION or core.get("authority") != AUTHORITY:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_AUTHORITY_MISMATCH")
    if core.get("task_id") != TASK_ID or core.get("workstream") != WORKSTREAM:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_TASK_MISMATCH")
    if core.get("pr_number") != PR_NUMBER or core.get("branch") != BRANCH:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_PR_MISMATCH")
    _sha(core.get("candidate_sha"), "candidate_sha")
    if _sha(core.get("expected_main_sha"), "expected_main_sha") != EXPECTED_MAIN_SHA:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_MAIN_MISMATCH")
    if not set(core.get("changed_paths") or []).issubset(ALLOWED_CHANGED_PATHS):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_SCOPE_VIOLATION")
    evidence = core.get("sandbox_evidence")
    if not isinstance(evidence, list) or not evidence or any(not isinstance(item, dict) or item.get("ok") is not True for item in evidence):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_EVIDENCE_INVALID")
    if core.get("sandbox_evidence_digest") != _digest(evidence):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_EVIDENCE_DIGEST_MISMATCH")
    return supplied


def _receipt_path(candidate_sha: str) -> str:
    return f"{RECEIPT_DIR}/{candidate_sha}.json"


def _read_receipt(github: Any, candidate_sha: str) -> dict[str, Any] | None:
    raw = github._request(
        "GET",
        f"/contents/{quote(_receipt_path(candidate_sha), safe='/')}?ref={quote(RECEIPT_REF, safe='/')}",
        allow_404=True,
    )
    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_READ_FAILED")
    try:
        parsed = json.loads(base64.b64decode(str(raw["content"])).decode("utf-8"))
    except Exception as exc:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_DECODE_FAILED") from exc
    return validate_receipt(parsed)


def _write_or_read_receipt(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _sha(receipt.get("candidate_sha"), "candidate_sha")
    existing = _read_receipt(github, candidate)
    if existing is not None:
        if existing != dict(receipt):
            raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_IDENTITY_COLLISION")
        return existing
    ref = github._request("GET", f"/git/ref/heads/{quote(RECEIPT_REF, safe='/')}", allow_404=True)
    if ref is None:
        github._request("POST", "/git/refs", json={"ref": f"refs/heads/{RECEIPT_REF}", "sha": candidate})
    content = base64.b64encode((_canonical(receipt) + "\n").encode("utf-8")).decode("ascii")
    github._request(
        "PUT",
        f"/contents/{quote(_receipt_path(candidate), safe='/')}",
        json={"message": f"MONSTER NBA PRA proof receipt {candidate[:12]}", "content": content, "branch": RECEIPT_REF},
    )
    readback = _read_receipt(github, candidate)
    if readback != dict(receipt):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_RECEIPT_READBACK_MISMATCH")
    return readback


def _matching_gate(check: Mapping[str, Any], candidate: str, digest: str) -> bool:
    output = dict(check.get("output") or {})
    return (
        check.get("name") == GATE_NAME
        and check.get("conclusion") == "success"
        and str(check.get("head_sha") or "") == candidate
        and str((check.get("app") or {}).get("id")) == GITHUB_APP_ID
        and digest in str(output.get("summary") or "")
        and "MONSTER_ONLY" in str(output.get("summary") or "")
    )


def _publish_gate_and_readback(github: Any, candidate_sha: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _sha(candidate_sha, "candidate_sha")
    digest = str(receipt.get("digest") or "")
    checks = github._request("GET", f"/commits/{candidate}/check-runs")
    for check in list((checks or {}).get("check_runs", [])):
        if _matching_gate(check, candidate, digest):
            return check
    github._request(
        "POST",
        "/check-runs",
        json={
            "name": GATE_NAME,
            "head_sha": candidate,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "MONSTER NBA PRA Proof Authority",
                "summary": f"authority=MONSTER_ONLY receipt={digest} task={TASK_ID}",
            },
        },
    )
    checks = github._request("GET", f"/commits/{candidate}/check-runs")
    for check in list((checks or {}).get("check_runs", [])):
        if _matching_gate(check, candidate, digest):
            return check
    raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_GATE_READBACK_FAILED")


async def prove_nba_pra_context_deadline(*, github: Any, sandbox: Any, expected_preview_sha: str) -> dict[str, Any]:
    preview_sha = _sha(expected_preview_sha, "preview_sha")
    pr = github._request("GET", f"/pulls/{PR_NUMBER}")
    if str(pr.get("state") or "") != "open":
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PR_NOT_OPEN")
    head = dict(pr.get("head") or {})
    base = dict(pr.get("base") or {})
    candidate = _sha(head.get("sha"), "candidate_sha")
    if candidate != preview_sha:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PREVIEW_HEAD_DRIFT")
    if str(head.get("ref") or "") != BRANCH or str(base.get("ref") or "") != BASE_BRANCH:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PR_IDENTITY_MISMATCH")
    if _sha(base.get("sha"), "pr_base_sha") != EXPECTED_MAIN_SHA:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PR_BASE_DRIFT")
    if _sha(github.main_sha(), "current_main_sha") != EXPECTED_MAIN_SHA:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_MAIN_IDENTITY_DRIFT")

    plan = github._content_json(PLAN_PATH, candidate)
    if plan.get("task_id") != TASK_ID or plan.get("workstream") != WORKSTREAM:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PLAN_IDENTITY_MISMATCH")
    if _sha(plan.get("source_main_sha"), "plan_main_sha") != EXPECTED_MAIN_SHA:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_PLAN_MAIN_DRIFT")

    compare = github._request("GET", f"/compare/{EXPECTED_MAIN_SHA}...{candidate}")
    if str(compare.get("status") or "") != "ahead":
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_CANDIDATE_ANCESTRY_MISMATCH")
    changed_paths = sorted(str(item.get("filename") or "") for item in compare.get("files", []))
    if not changed_paths or not set(changed_paths).issubset(ALLOWED_CHANGED_PATHS):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_CHANGED_PATH_SCOPE_VIOLATION")

    tree = github.tree_blobs(candidate)
    artifact_map = _blob_map(tree, plan.get("artifacts") or [], "artifact")
    dependency_map = _blob_map(tree, plan.get("dependencies") or [], "dependency")
    sandbox_result = await sandbox.execute(
        candidate_sha=candidate,
        task_id=TASK_ID,
        github_token=github.installation_token(),
        timeout_seconds=int(plan.get("timeout_seconds", 900)),
    )
    if sandbox_result.candidate_sha != candidate or sandbox_result.task_id != TASK_ID:
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_SANDBOX_IDENTITY_MISMATCH")
    if _canonical(sandbox_result.plan) != _canonical(plan):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_SANDBOX_PLAN_DRIFT")
    evidence = [item.model_dump(mode="json") for item in sandbox_result.evidence]
    if not sandbox_result.ok or not evidence or any(item.get("ok") is not True for item in evidence):
        raise MonsterNbaPraProofFailure("MONSTER_NBA_PRA_PROOF_SANDBOX_NOT_GREEN")

    receipt = build_receipt(
        candidate_sha=candidate,
        expected_main_sha=EXPECTED_MAIN_SHA,
        changed_paths=changed_paths,
        artifact_map=artifact_map,
        dependency_map=dependency_map,
        evidence=evidence,
        plan=plan,
    )
    readback = _write_or_read_receipt(github, receipt)
    validate_receipt(readback)
    check = _publish_gate_and_readback(github, candidate, readback)
    return {
        "status": "GREEN",
        "authority": AUTHORITY,
        "version": VERSION,
        "task_id": TASK_ID,
        "candidate_sha": candidate,
        "expected_main_sha": EXPECTED_MAIN_SHA,
        "receipt_ref": RECEIPT_REF,
        "receipt_digest": readback["digest"],
        "gate_name": GATE_NAME,
        "gate_check_run_id": check.get("id"),
        "gate_app_id": str((check.get("app") or {}).get("id") or ""),
        "readback_verified": True,
        "shared_runless_state_used": False,
    }
