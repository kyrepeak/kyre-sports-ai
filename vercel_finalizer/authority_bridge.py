from __future__ import annotations

from typing import Any

from vercel_finalizer.authority import AuthoritySnapshot, FinalizerAuthorityError
from vercel_finalizer.gate_publication import GateClaimDecision, GatePublicationError, project_claim_result

BRIDGE_PATH = "/functions/v1/guardian-finalizer-authority-bridge-v1"


def _headers(app_jwt: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {app_jwt}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(client: Any, *, supabase_url: str, app_jwt: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        supabase_url.rstrip("/") + BRIDGE_PATH,
        headers=_headers(app_jwt),
        json=payload,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            detail = str(body.get("error") or body.get("detail") or "") if isinstance(body, dict) else ""
        except Exception:
            detail = ""
        if detail.startswith("FINALIZER_"):
            if "GATE_" in detail:
                raise GatePublicationError(detail)
            raise FinalizerAuthorityError(detail)
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE")
    try:
        body = response.json()
    except Exception as exc:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE") from exc
    if not isinstance(body, dict):
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE")
    return dict(body)


def authority_bridge_health(client: Any, *, supabase_url: str, app_jwt: str) -> dict[str, Any]:
    body = _post(
        client,
        supabase_url=supabase_url,
        app_jwt=app_jwt,
        payload={"action": "health"},
    )
    if body.get("status") != "ok" or str(body.get("app_id")) != "5204253":
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE")
    return body


def resolve_authority_via_bridge(
    client: Any,
    *,
    supabase_url: str,
    app_jwt: str,
    workstream: str,
    task_id: str,
    candidate_sha: str,
    fencing_generation: int,
) -> AuthoritySnapshot:
    body = _post(
        client,
        supabase_url=supabase_url,
        app_jwt=app_jwt,
        payload={
            "action": "resolve_authority",
            "workstream": workstream,
            "task_id": task_id,
            "candidate_sha": candidate_sha,
            "fencing_generation": int(fencing_generation),
        },
    )
    row = body.get("authority")
    if not isinstance(row, dict):
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE")
    try:
        return AuthoritySnapshot(
            proof_id=str(row["proof_id"]),
            task_id=str(row["task_id"]),
            workstream=str(row["workstream"]),
            candidate_sha=str(row["candidate_sha"]),
            fencing_generation=int(row["fencing_generation"]),
            proof_fingerprint=str(row.get("proof_fingerprint") or ""),
            state=str(row.get("state") or ""),
            scope_lease_id=str(row.get("scope_lease_id") or ""),
        )
    except Exception as exc:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_BRIDGE_UNAVAILABLE") from exc


def claim_publication_via_bridge(
    client: Any,
    *,
    supabase_url: str,
    app_jwt: str,
    proof_id: str,
    candidate_sha: str,
    fencing_generation: int,
    proof_digest: str,
    claim_token: str,
) -> GateClaimDecision:
    body = _post(
        client,
        supabase_url=supabase_url,
        app_jwt=app_jwt,
        payload={
            "action": "claim_publication",
            "proof_id": proof_id,
            "candidate_sha": candidate_sha,
            "fencing_generation": int(fencing_generation),
            "proof_digest": proof_digest,
            "claim_token": claim_token,
        },
    )
    return project_claim_result(body)


def complete_publication_via_bridge(
    client: Any,
    *,
    supabase_url: str,
    app_jwt: str,
    proof_id: str,
    claim_token: str,
    gate_check_run_id: int,
) -> int:
    body = _post(
        client,
        supabase_url=supabase_url,
        app_jwt=app_jwt,
        payload={
            "action": "complete_publication",
            "proof_id": proof_id,
            "claim_token": claim_token,
            "gate_check_run_id": int(gate_check_run_id),
        },
    )
    check_id = int(body.get("gate_check_run_id") or 0)
    if check_id <= 0:
        raise GatePublicationError("FINALIZER_GATE_COMPLETION_INVALID")
    return check_id
