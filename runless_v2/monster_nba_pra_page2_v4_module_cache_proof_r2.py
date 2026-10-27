"""MONSTER-only App-5204253 proof for NBA PRA Page 2 V4 module cache R2."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any
from urllib.parse import quote

VERSION = "MONSTER_NBA_PRA_PAGE2_V4_MODULE_CACHE_PROOF_R2"
AUTHORITY = "MONSTER_ONLY"
TASK_ID = "monster-nba-pra-page2-v4-module-cache-r2"
WORKSTREAM = TASK_ID
PR_NUMBER = 1887
CANDIDATE_BRANCH = "monster-nba-pra-page2-v4-module-cache-r2"
PROOF_BRANCH = "monster-nba-pra-page2-v4-module-cache-proof-r2"
EXPECTED_MAIN_SHA = "262cc4cbf313b22cefbd3f31b90d811e7f1aea7d"
TARGET_CANDIDATE_SHA = "2d98a27331eb6b65367491fbb6959b84fb6462ac"
BASE_APP_BLOB = "7f0ee61f8cf3fa38d41412e724d5ca1f23b0989c"
TARGET_APP_BLOB = "b198c271b2aa0ec825f35f4e5da6ef3012d60d1f"
AUTHORIZATION_ID = "AUTH-MONSTER-NBA-PRA-PAGE2-V4-MODULE-CACHE-R2-1887"
GATE_NAME = "runless-final-gate"
GITHUB_APP_ID = "5204253"
RECEIPT_REF = "monster-step2g-proof-receipts-v1"
RECEIPT_DIR = "devsystem/monster_step2g_module_cache_proof_receipts"
PLAN_PATH = f"devsystem/runless_proof_plans/{TASK_ID}.json"
EXPECTED_CHANGED_PATHS = frozenset({
    "app.py",
    PLAN_PATH,
    "docs/superpowers/plans/2026-10-26-monster-nba-pra-page2-v4-module-cache-r2.md",
    "tests/test_monster_nba_pra_page2_v4_module_cache_r2.py",
})
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
_FOREIGN_RE = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.I)


class MonsterModuleCacheProofFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


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
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_FOREIGN_EVIDENCE_FORBIDDEN")


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise MonsterModuleCacheProofFailure(f"MONSTER_MODULE_CACHE_{label.upper()}_INVALID")
    return text


def _decode_text(github: Any, path: str, ref: str) -> str:
    raw = github._request("GET", f"/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}")
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_CONTENT_READ_FAILED")
    return base64.b64decode(str(raw["content"])).decode("utf-8")


def _expected_app(base: str) -> str:
    anchor = 'sys.modules.pop("nfl_moneyline_hub_v20", None)\nimportlib.invalidate_caches()'
    replacement = (
        'sys.modules.pop("nfl_moneyline_hub_v20", None)\n'
        'sys.modules.pop("nba_pra_page2_sync_v1", None)\n'
        'sys.modules.pop("nba_pra_page2_command_center_v4", None)\n'
        'importlib.invalidate_caches()'
    )
    if base.count(anchor) != 1:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_APP_ANCHOR_MISMATCH")
    return base.replace(anchor, replacement, 1)


def _blob_map(tree: Mapping[str, Any], paths: Sequence[str], label: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(set(map(str, paths))):
        blob = str(tree.get(path) or "").strip().lower()
        if not _SHA_RE.fullmatch(blob):
            raise MonsterModuleCacheProofFailure(f"MONSTER_MODULE_CACHE_{label.upper()}_MISSING:{path}")
        out[path] = blob
    return out


def _receipt_path() -> str:
    return f"{RECEIPT_DIR}/{TARGET_CANDIDATE_SHA}.json"


def _read_receipt(github: Any) -> dict[str, Any] | None:
    raw = github._request("GET", f"/contents/{quote(_receipt_path(), safe='/')}?ref={quote(RECEIPT_REF, safe='')}", allow_404=True)
    if raw is None:
        return None
    value = json.loads(base64.b64decode(str(raw["content"])).decode("utf-8"))
    return validate_receipt(value)


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    supplied = deepcopy(dict(value))
    _reject_foreign(supplied)
    digest = str(supplied.get("digest") or "").lower()
    if not _DIGEST_RE.fullmatch(digest):
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_RECEIPT_DIGEST_INVALID")
    core = dict(supplied)
    core.pop("digest", None)
    if _digest(core) != digest:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_RECEIPT_DIGEST_MISMATCH")
    if core.get("authority") != AUTHORITY or core.get("task_id") != TASK_ID or core.get("candidate_sha") != TARGET_CANDIDATE_SHA:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_RECEIPT_IDENTITY_MISMATCH")
    return supplied


def _write_or_read_receipt(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    existing = _read_receipt(github)
    if existing is not None:
        if existing != dict(receipt):
            raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_RECEIPT_COLLISION")
        return existing
    content = base64.b64encode((_canonical(receipt) + "\n").encode()).decode()
    github._request("PUT", f"/contents/{quote(_receipt_path(), safe='/')}", json={
        "message": f"MONSTER module cache proof {TARGET_CANDIDATE_SHA[:12]}",
        "content": content,
        "branch": RECEIPT_REF,
    })
    readback = _read_receipt(github)
    if readback != dict(receipt):
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_RECEIPT_READBACK_MISMATCH")
    return readback


def _matching_gate(check: Mapping[str, Any], digest: str) -> bool:
    output = dict(check.get("output") or {})
    return (
        check.get("name") == GATE_NAME
        and check.get("conclusion") == "success"
        and str(check.get("head_sha") or "") == TARGET_CANDIDATE_SHA
        and str((check.get("app") or {}).get("id")) == GITHUB_APP_ID
        and AUTHORITY in str(output.get("summary") or "")
        and digest in str(output.get("summary") or "")
    )


def _publish_gate(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    digest = str(receipt["digest"])
    checks = github._request("GET", f"/commits/{TARGET_CANDIDATE_SHA}/check-runs")
    for check in (checks or {}).get("check_runs", []):
        if _matching_gate(check, digest):
            return dict(check)
    github._request("POST", "/check-runs", json={
        "name": GATE_NAME,
        "head_sha": TARGET_CANDIDATE_SHA,
        "status": "completed",
        "conclusion": "success",
        "output": {
            "title": "MONSTER NBA PRA Page 2 V4 Module Cache R2",
            "summary": f"authority={AUTHORITY} receipt={digest} task={TASK_ID}",
        },
    })
    checks = github._request("GET", f"/commits/{TARGET_CANDIDATE_SHA}/check-runs")
    for check in (checks or {}).get("check_runs", []):
        if _matching_gate(check, digest):
            return dict(check)
    raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_GATE_READBACK_FAILED")


async def prove_module_cache_r2(*, github: Any, sandbox: Any, expected_preview_sha: str) -> dict[str, Any]:
    preview_sha = _sha(expected_preview_sha, "preview_sha")
    proof_ref = github._request("GET", f"/git/ref/heads/{quote(PROOF_BRANCH, safe='')}")
    if _sha(((proof_ref or {}).get("object") or {}).get("sha"), "proof_branch_sha") != preview_sha:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_PROOF_PREVIEW_DRIFT")
    if _sha(github.main_sha(), "main_sha") != EXPECTED_MAIN_SHA:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_MAIN_DRIFT")

    pr = github._request("GET", f"/pulls/{PR_NUMBER}")
    head, base = dict(pr.get("head") or {}), dict(pr.get("base") or {})
    if str(pr.get("state") or "") != "open" or str(head.get("ref") or "") != CANDIDATE_BRANCH or str(base.get("ref") or "") != "main":
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_PR_IDENTITY_MISMATCH")
    if _sha(head.get("sha"), "candidate_sha") != TARGET_CANDIDATE_SHA or _sha(base.get("sha"), "pr_base_sha") != EXPECTED_MAIN_SHA:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_PR_HEAD_OR_BASE_DRIFT")

    compare = github._request("GET", f"/compare/{EXPECTED_MAIN_SHA}...{TARGET_CANDIDATE_SHA}")
    changed_paths = sorted(str(item.get("filename") or "") for item in compare.get("files", []))
    if str(compare.get("status") or "") != "ahead" or set(changed_paths) != set(EXPECTED_CHANGED_PATHS):
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_SCOPE_OR_ANCESTRY_INVALID")

    main_tree, candidate_tree = github.tree_blobs(EXPECTED_MAIN_SHA), github.tree_blobs(TARGET_CANDIDATE_SHA)
    if str(main_tree.get("app.py") or "").lower() != BASE_APP_BLOB or str(candidate_tree.get("app.py") or "").lower() != TARGET_APP_BLOB:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_APP_BLOB_MISMATCH")
    base_app = _decode_text(github, "app.py", EXPECTED_MAIN_SHA)
    candidate_app = _decode_text(github, "app.py", TARGET_CANDIDATE_SHA)
    if candidate_app != _expected_app(base_app):
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_APP_DELTA_INVALID")

    plan = github._content_json(PLAN_PATH, TARGET_CANDIDATE_SHA)
    if plan.get("task_id") != TASK_ID or plan.get("workstream") != WORKSTREAM or _sha(plan.get("source_main_sha"), "plan_main") != EXPECTED_MAIN_SHA:
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_PLAN_IDENTITY_MISMATCH")
    artifact_map = _blob_map(candidate_tree, plan.get("artifacts") or [], "artifact")
    dependency_map = _blob_map(candidate_tree, plan.get("dependencies") or [], "dependency")

    sandbox_result = await sandbox.execute(candidate_sha=TARGET_CANDIDATE_SHA, task_id=TASK_ID, github_token=github.installation_token(), timeout_seconds=int(plan.get("timeout_seconds", 600)))
    evidence = [item.model_dump(mode="json") for item in sandbox_result.evidence]
    if sandbox_result.candidate_sha != TARGET_CANDIDATE_SHA or sandbox_result.task_id != TASK_ID or _canonical(sandbox_result.plan) != _canonical(plan):
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_SANDBOX_IDENTITY_MISMATCH")
    if not sandbox_result.ok or not evidence or any(item.get("ok") is not True for item in evidence):
        raise MonsterModuleCacheProofFailure("MONSTER_MODULE_CACHE_SANDBOX_NOT_GREEN")

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
        "authorization_id": AUTHORIZATION_ID,
        "one_active_problem": True,
        "anti_loop": {"blind_retry_allowed": False, "duplicate_proof_lane_allowed": False},
        "one_use_thaw": {"path": "app.py", "from_blob": BASE_APP_BLOB, "to_blob": TARGET_APP_BLOB, "shared_registry_consumed": False},
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
    gate = _publish_gate(github, receipt)
    return {"state": "MERGE_AUTHORIZED", "authority": AUTHORITY, "candidate_sha": TARGET_CANDIDATE_SHA, "receipt_digest": receipt["digest"], "gate_check_run_id": int(gate["id"]), "github_app_id": str((gate.get("app") or {}).get("id") or ""), "failure_class": "NONE"}
