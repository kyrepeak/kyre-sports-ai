from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from vercel_finalizer.receipt_contract import finalization_proof_digest, validate_receipt
from vercel_finalizer.authority import AuthoritySnapshot


class ReceiptBindingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReceiptBinding:
    proof_id: str
    task_id: str
    workstream: str
    candidate_sha: str
    fencing_generation: int
    proof_fingerprint: str
    proof_digest: str


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def resolve_receipt_binding(
    client: Any,
    *,
    token: str,
    repository: str,
    receipt_ref: str,
    receipt_path: str,
    authority: AuthoritySnapshot,
    requested_proof_digest: str,
) -> ReceiptBinding:
    if authority.state != "RUNLESS_FINAL_GATE":
        raise ReceiptBindingError("FINALIZER_RECEIPT_STATE_INVALID")

    path = f"{receipt_path.rstrip('/')}/{authority.proof_id}.json"
    url = (
        f"https://api.github.com/repos/{repository}/contents/"
        f"{quote(path, safe='/')}?ref={quote(receipt_ref, safe='')}"
    )
    response = client.get(url, headers=_headers(token))
    if response.status_code == 404:
        raise ReceiptBindingError("FINALIZER_RECEIPT_NOT_FOUND")
    if response.status_code >= 400:
        raise ReceiptBindingError("FINALIZER_RECEIPT_STORE_UNAVAILABLE")

    try:
        raw = response.json()
        receipt = json.loads(base64.b64decode(raw["content"]).decode())
        validate_receipt(receipt)
    except Exception as exc:
        raise ReceiptBindingError("FINALIZER_RECEIPT_TAMPERED") from exc

    identity = (
        receipt.get("proof_id") == authority.proof_id
        and receipt.get("task_id") == authority.task_id
        and receipt.get("workstream") == authority.workstream
        and str(receipt.get("candidate_sha") or "").lower() == authority.candidate_sha.lower()
        and receipt.get("proof_fingerprint") == authority.proof_fingerprint
        and receipt.get("failure_class") == "NONE"
    )
    if not identity:
        raise ReceiptBindingError("FINALIZER_RECEIPT_IDENTITY_MISMATCH")

    proof_digest = finalization_proof_digest(receipt)
    if requested_proof_digest.lower() != proof_digest.lower():
        raise ReceiptBindingError("FINALIZER_PROOF_DIGEST_MISMATCH")

    return ReceiptBinding(
        proof_id=authority.proof_id,
        task_id=authority.task_id,
        workstream=authority.workstream,
        candidate_sha=authority.candidate_sha,
        fencing_generation=authority.fencing_generation,
        proof_fingerprint=authority.proof_fingerprint,
        proof_digest=proof_digest,
    )
