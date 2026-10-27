"""Isolated MONSTER proof publisher for WNBA PRA upcoming-only R2 final-card guard."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import quote

VERSION = "MONSTER_WNBA_PRA_UPCOMING_ONLY_R2_FINAL_CARD_PROOF"
AUTHORITY = "MONSTER_ONLY"
TASK_ID = "monster-wnba-pra-upcoming-only-r2-final-card"
WORKSTREAM = TASK_ID
PR_NUMBER = 1890
BRANCH = "monster-wnba-pra-upcoming-only-r2-final-card"
BASE_BRANCH = "main"
EXPECTED_MAIN_SHA = "c8575399c7f0c1c7f3e9a68426fed81d68571153"
GATE_NAME = "runless-final-gate"
GITHUB_APP_ID = "5204253"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_DIR = "devsystem/runless_proof_receipts"
PLAN_PATH = f"devsystem/runless_proof_plans/{TASK_ID}.json"

ALLOWED_CHANGED_PATHS = frozenset({
    "wnba_pra_page1_ultra_stier_v3.py",
    "wnba_pra_hub_v3612.py",
    "tests/test_monster_wnba_pra_upcoming_only_r2_final_card.py",
    "devsystem/task_ledgers/monster-wnba-pra-upcoming-only-r2-final-card.json",
    "docs/superpowers/plans/2026-10-26-monster-wnba-pra-upcoming-only-r2-final-card.md",
    "devsystem/runless_proof_plans/monster-wnba-pra-upcoming-only-r2-final-card.json",
    "runless_v2/monster_wnba_pra_upcoming_only_r2_final_card_proof.py",
    "runless_v2/__init__.py",
})
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class ProofFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise ProofFailure(f"MONSTER_WNBA_R2_PROOF_{label.upper()}_INVALID")
    return text


def _blob_map(tree: Mapping[str, Any], paths: Sequence[str], label: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(set(str(item) for item in paths)):
        blob = str(tree.get(path) or "").strip().lower()
        if not _SHA_RE.fullmatch(blob):
            raise ProofFailure(f"MONSTER_WNBA_R2_PROOF_{label.upper()}_MISSING:{path}")
        out[path] = blob
    return out


def _receipt_path(candidate: str) -> str:
    return f"{RECEIPT_DIR}/{TASK_ID}-{candidate[:16]}.json"


def _read_receipt(github: Any, candidate: str) -> dict[str, Any] | None:
    raw = github._request(
        "GET",
        f"/contents/{quote(_receipt_path(candidate), safe='/')}?ref={quote(RECEIPT_REF, safe='/')}",
        allow_404=True,
    )
    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_RECEIPT_READ_FAILED")
    parsed = json.loads(base64.b64decode(str(raw["content"])).decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_RECEIPT_INVALID")
    core = dict(parsed)
    supplied = str(core.pop("digest", ""))
    if supplied != _digest(core):
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_RECEIPT_DIGEST_MISMATCH")
    return parsed


def _write_receipt(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _sha(receipt.get("candidate_sha"), "candidate_sha")
    existing = _read_receipt(github, candidate)
    if existing is not None:
        if existing != dict(receipt):
            raise ProofFailure("MONSTER_WNBA_R2_PROOF_RECEIPT_COLLISION")
        return existing
    github._ensure_receipt_ref(candidate)
    content = base64.b64encode((_canonical(receipt) + "\n").encode("utf-8")).decode("ascii")
    github._request(
        "PUT",
        f"/contents/{quote(_receipt_path(candidate), safe='/')}",
        json={
            "message": f"MONSTER WNBA R2 final-card proof {candidate[:12]}",
            "content": content,
            "branch": RECEIPT_REF,
        },
    )
    readback = _read_receipt(github, candidate)
    if readback != dict(receipt):
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_RECEIPT_READBACK_MISMATCH")
    return readback


def _matching_gate(check: Mapping[str, Any], candidate: str, digest: str) -> bool:
    output = dict(check.get("output") or {})
    return (
        check.get("name") == GATE_NAME
        and check.get("conclusion") == "success"
        and str(check.get("head_sha") or "") == candidate
        and str((check.get("app") or {}).get("id")) == GITHUB_APP_ID
        and digest in str(output.get("summary") or "")
        and AUTHORITY in str(output.get("summary") or "")
    )


def _publish_gate(github: Any, candidate: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
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
                "title": "MONSTER WNBA PRA Upcoming-Only R2 Final-Card Proof",
                "summary": f"authority={AUTHORITY} receipt={digest} task={TASK_ID}",
            },
        },
    )
    checks = github._request("GET", f"/commits/{candidate}/check-runs")
    for check in list((checks or {}).get("check_runs", [])):
        if _matching_gate(check, candidate, digest):
            return check
    raise ProofFailure("MONSTER_WNBA_R2_PROOF_GATE_READBACK_FAILED")


async def prove(*, github: Any, sandbox: Any, expected_preview_sha: str) -> dict[str, Any]:
    preview = _sha(expected_preview_sha, "preview_sha")
    pr = github._request("GET", f"/pulls/{PR_NUMBER}")
    if str(pr.get("state") or "") != "open":
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_PR_NOT_OPEN")
    head = dict(pr.get("head") or {})
    base = dict(pr.get("base") or {})
    candidate = _sha(head.get("sha"), "candidate_sha")
    if candidate != preview:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_PREVIEW_HEAD_DRIFT")
    if str(head.get("ref") or "") != BRANCH or str(base.get("ref") or "") != BASE_BRANCH:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_PR_IDENTITY_MISMATCH")
    if _sha(base.get("sha"), "pr_base_sha") != EXPECTED_MAIN_SHA:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_PR_BASE_DRIFT")
    if _sha(github.main_sha(), "current_main_sha") != EXPECTED_MAIN_SHA:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_MAIN_IDENTITY_DRIFT")

    plan = github._content_json(PLAN_PATH, candidate)
    if plan.get("task_id") != TASK_ID or plan.get("workstream") != WORKSTREAM:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_PLAN_IDENTITY_MISMATCH")
    if _sha(plan.get("source_main_sha"), "plan_main_sha") != EXPECTED_MAIN_SHA:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_PLAN_MAIN_DRIFT")
    if plan.get("required_check") != GATE_NAME or str(plan.get("required_check_app_id")) != GITHUB_APP_ID:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_GATE_POLICY_DRIFT")

    compare = github._request("GET", f"/compare/{EXPECTED_MAIN_SHA}...{candidate}")
    if str(compare.get("status") or "") != "ahead":
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_ANCESTRY_MISMATCH")
    changed_paths = sorted(str(item.get("filename") or "") for item in compare.get("files", []))
    if not changed_paths or not set(changed_paths).issubset(ALLOWED_CHANGED_PATHS):
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_CHANGED_PATH_SCOPE_VIOLATION")

    tree = github.tree_blobs(candidate)
    artifact_map = _blob_map(tree, plan.get("artifacts") or [], "artifact")
    dependency_map = _blob_map(tree, plan.get("dependencies") or [], "dependency")
    result = await sandbox.execute(
        candidate_sha=candidate,
        task_id=TASK_ID,
        github_token=github.installation_token(),
        timeout_seconds=int(plan.get("timeout_seconds", 600)),
    )
    if result.candidate_sha != candidate or result.task_id != TASK_ID:
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_SANDBOX_IDENTITY_MISMATCH")
    if _canonical(result.plan) != _canonical(plan):
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_SANDBOX_PLAN_DRIFT")
    evidence = [item.model_dump(mode="json") for item in result.evidence]
    if not result.ok or not evidence or any(item.get("ok") is not True for item in evidence):
        raise ProofFailure("MONSTER_WNBA_R2_PROOF_SANDBOX_NOT_GREEN")

    core = {
        "schema_version": 1,
        "version": VERSION,
        "authority": AUTHORITY,
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": candidate,
        "expected_main_sha": EXPECTED_MAIN_SHA,
        "pr_number": PR_NUMBER,
        "branch": BRANCH,
        "changed_paths": changed_paths,
        "artifact_map": artifact_map,
        "dependency_map": dependency_map,
        "sandbox_evidence_digest": _digest(evidence),
        "plan_digest": _digest(plan),
        "gate_name": GATE_NAME,
        "github_app_id": GITHUB_APP_ID,
        "api2_state_used": False,
    }
    receipt = dict(core)
    receipt["digest"] = _digest(core)
    readback = _write_receipt(github, receipt)
    check = _publish_gate(github, candidate, readback)
    return {
        "status": "GREEN",
        "authority": AUTHORITY,
        "candidate_sha": candidate,
        "receipt_digest": readback["digest"],
        "gate_check_run_id": check.get("id"),
        "gate_app_id": str((check.get("app") or {}).get("id") or ""),
        "readback_verified": True,
    }
