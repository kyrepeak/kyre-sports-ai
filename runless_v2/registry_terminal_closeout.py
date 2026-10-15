from __future__ import annotations

import base64
import json
import re
from typing import Any, TYPE_CHECKING
from urllib.parse import quote

import httpx

from devsystem.canonical_completion_ledger_autoheal_v1 import resolve_and_plan_ledger_autoheal
from devsystem.canonical_completion_resolver_v1 import resolve_completion

from .models import RegistryForwardPortRequest
from .registry_terminal_reconcile import request_registry_forward_port as _reconcile_registry
from .registry_thaw import _error, _read_snapshot

if TYPE_CHECKING:
    from .github_authority import GithubAuthority

APP_ID_EXPECTED = 5204253
TASK_LEDGER_DIR = "devsystem/task_ledgers"


def _gate_and_receipt(authority: GithubAuthority, candidate_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = []
    for check in authority._check_runs(candidate_sha):
        if (
            str(check.get("name") or "") == "runless-final-gate"
            and str(check.get("conclusion") or "").lower() == "success"
            and str(check.get("head_sha") or "") == candidate_sha
            and int((check.get("app") or {}).get("id") or 0) == APP_ID_EXPECTED
        ):
            matches.append(check)
    if len(matches) != 1:
        raise _error("TERMINAL_LEDGER_GATE_IDENTITY_MISMATCH")
    check = matches[0]
    summary = str((check.get("output") or {}).get("summary") or "")
    parsed = re.search(r"receipt=([0-9a-f]{64})\s+proof=([^\s]+)", summary)
    if not parsed:
        raise _error("TERMINAL_LEDGER_GATE_SUMMARY_INVALID")
    digest, proof_id = parsed.groups()
    receipt = authority._read_receipt(proof_id)
    if not isinstance(receipt, dict) or str(receipt.get("digest") or "") != digest:
        raise _error("TERMINAL_LEDGER_RECEIPT_READBACK_MISMATCH")
    gate = {
        "name": "runless-final-gate",
        "conclusion": "success",
        "head_sha": candidate_sha,
        "receipt_digest": digest,
        "app_id": APP_ID_EXPECTED,
        "check_run_id": int(check.get("id") or 0),
    }
    return gate, receipt


def _merge_evidence(authority: GithubAuthority, request: RegistryForwardPortRequest) -> dict[str, Any]:
    commit = authority.commit(request.merged_main_sha)
    parents = [str(item.get("sha") or "") for item in (commit.get("parents") or []) if isinstance(item, dict)]
    return {
        "contains_candidate": request.candidate_sha in parents,
        "candidate_sha": request.candidate_sha,
        "merged_main_sha": request.merged_main_sha,
    }


def _authoritative_pr(authority: GithubAuthority, request: RegistryForwardPortRequest) -> int:
    pulls = authority._request("GET", f"/commits/{request.candidate_sha}/pulls")
    matches = [
        item for item in (pulls or [])
        if isinstance(item, dict)
        and str(((item.get("head") or {}).get("sha") or "")) == request.candidate_sha
        and str(item.get("merge_commit_sha") or "") == request.merged_main_sha
        and item.get("merged_at")
    ]
    if len(matches) != 1:
        raise _error("TERMINAL_LEDGER_PR_PROVENANCE_MISMATCH")
    return int(matches[0]["number"])


def _read_task_ledger(authority: GithubAuthority, workstream: str) -> tuple[str, dict[str, Any]]:
    path = f"{TASK_LEDGER_DIR}/{workstream}.json"
    raw = authority._request("GET", f"/contents/{quote(path, safe='/')}?ref=main")
    blob_sha = str((raw or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", blob_sha) or (raw or {}).get("encoding") != "base64":
        raise _error("TERMINAL_LEDGER_READ_FAILED")
    try:
        ledger = json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
    except Exception as exc:
        raise _error("TERMINAL_LEDGER_DECODE_FAILED") from exc
    return blob_sha, ledger


def _heal_task_ledger(
    authority: GithubAuthority,
    request: RegistryForwardPortRequest,
    *,
    freeze_token: str,
) -> dict[str, Any]:
    snapshot = _read_snapshot(authority, repository=request.repository)
    registry = snapshot["registry"]
    entry = (registry.get("entries") or {}).get(freeze_token)
    if not isinstance(entry, dict) or entry.get("status") != "FROZEN":
        raise _error("TERMINAL_LEDGER_FREEZE_NOT_CANONICAL")

    gate, receipt = _gate_and_receipt(authority, request.candidate_sha)
    if str(receipt.get("task_id") or "") != request.workstream:
        raise _error("TERMINAL_LEDGER_RECEIPT_TASK_MISMATCH")
    merge = _merge_evidence(authority, request)
    blob_sha, ledger = _read_task_ledger(authority, request.workstream)
    plan = resolve_and_plan_ledger_autoheal(
        task_id=request.workstream,
        freeze_token=freeze_token,
        ledger=ledger,
        registry=registry,
        receipt=receipt,
        gate=gate,
        merge_evidence=merge,
    )
    decision = str(plan.get("decision") or "")
    if decision == "LEDGER_ALREADY_ALIGNED":
        return {"task_ledger_reconciled": False, "task_ledger_reused": True}
    if decision != "LEDGER_AUTOHEAL_PLANNED" or plan.get("write_required") is not True:
        raise _error("TERMINAL_LEDGER_AUTOHEAL_BLOCKED:" + decision)

    healed = plan.get("healed_ledger")
    if not isinstance(healed, dict):
        raise _error("TERMINAL_LEDGER_AUTOHEAL_INVALID")
    proof_id = str(receipt.get("proof_id") or "")
    pr_number = _authoritative_pr(authority, request)
    healed["authoritative_pr"] = pr_number
    healed["state"] = "GREEN_FROZEN"
    healed["status"] = "DONE"
    healed.setdefault("runless", {})["proof_id"] = proof_id
    healed["runless"]["receipt_digest"] = str(receipt.get("digest") or "")
    healed["runless"]["gate_check_run_id"] = gate["check_run_id"]
    healed["runless"]["merged_main_sha"] = request.merged_main_sha
    healed.setdefault("acceptance", {})["exact_head_runless_green"] = True
    healed["acceptance"]["merged_main_verified"] = True
    healed["acceptance"]["frozen_verified"] = True
    healed["green_plus_frozen_claimed"] = True
    healed["next_legal_action"] = "NONE_TERMINAL_GREEN_FROZEN"

    post = resolve_completion(
        task_id=request.workstream,
        freeze_token=freeze_token,
        ledger=healed,
        registry=registry,
        receipt=receipt,
        gate=gate,
        merge_evidence=merge,
    )
    if not (
        post.get("complete") is True
        and post.get("status") == "GREEN_FROZEN"
        and post.get("decision") == "CANONICAL_GREEN_FROZEN"
        and post.get("ledger_stale") is False
    ):
        raise _error("TERMINAL_LEDGER_POST_HEAL_CANONICAL_MISMATCH")

    text = json.dumps(healed, indent=2, ensure_ascii=True) + "\n"
    path = f"{TASK_LEDGER_DIR}/{request.workstream}.json"
    try:
        written = authority._request(
            "PUT",
            f"/contents/{quote(path, safe='/')}",
            json={
                "message": f"finalization: autoheal {request.workstream} terminal ledger",
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                "branch": "main",
                "sha": blob_sha,
            },
        )
    except httpx.HTTPStatusError as exc:
        message = ""
        try:
            message = str((exc.response.json() or {}).get("message") or "")
        except Exception:
            message = str(exc.response.text or "")
        if "Changes must be made through a pull request" in message:
            raise _error("TERMINAL_LEDGER_BRANCH_PROTECTION_BLOCKED") from exc
        if exc.response.status_code in (409, 422):
            raise _error("TERMINAL_LEDGER_CAS_CONFLICT") from exc
        if exc.response.status_code == 403:
            raise _error("TERMINAL_LEDGER_APP_PERMISSION_BLOCKED") from exc
        raise

    commit_sha = str(((written or {}).get("commit") or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise _error("TERMINAL_LEDGER_WRITE_FAILED")
    _, readback = _read_task_ledger(authority, request.workstream)
    if readback != healed:
        raise _error("TERMINAL_LEDGER_READBACK_MISMATCH")
    return {
        "task_ledger_reconciled": True,
        "task_ledger_reused": False,
        "task_ledger_commit_sha": commit_sha,
        "task_ledger_pr": pr_number,
        "task_ledger_status": "DONE",
        "task_ledger_state": "GREEN_FROZEN",
    }


def request_registry_forward_port(authority: GithubAuthority, request: RegistryForwardPortRequest) -> dict[str, Any]:
    result = _reconcile_registry(authority, request)
    freeze_token = str(result.get("freeze_token") or "")
    if result.get("state") != "FROZEN" or not freeze_token:
        return result
    healed = _heal_task_ledger(authority, request, freeze_token=freeze_token)
    return {**result, **healed}
