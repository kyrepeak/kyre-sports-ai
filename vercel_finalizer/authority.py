from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class FinalizerAuthorityError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthoritySnapshot:
    proof_id: str
    task_id: str
    workstream: str
    candidate_sha: str
    fencing_generation: int
    proof_fingerprint: str
    state: str
    scope_lease_id: str


@dataclass(frozen=True)
class RecoverySnapshot:
    proof_id: str
    task_id: str
    workstream: str
    candidate_sha: str
    fencing_generation: int
    proof_fingerprint: str
    state: str
    scope_lease_id: str
    failure_class: str
    detail: str
    restart_required: bool
    next_legal_action: str


def _headers(service_role_key: str) -> dict[str, str]:
    headers = {
        "apikey": service_role_key,
        "Accept": "application/json",
        "Accept-Profile": "runless_v2",
    }
    if not service_role_key.startswith(("sb_secret_", "sb_publishable_")):
        headers["Authorization"] = f"Bearer {service_role_key}"
    return headers


def _read(client: Any, url: str, headers: dict[str, str], params: dict[str, str]) -> list[dict[str, Any]]:
    response = client.get(url, headers=headers, params=params)
    if response.status_code >= 400:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_STORE_UNAVAILABLE")
    try:
        rows = response.json()
    except Exception as exc:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_STORE_UNAVAILABLE") from exc
    if not isinstance(rows, list):
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_STORE_UNAVAILABLE")
    return [dict(row) for row in rows]


def _exact_proof_rows(
    rows: list[dict[str, Any]],
    *,
    workstream: str,
    task_id: str,
    candidate_sha: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("workstream") or "") == workstream
        and str(row.get("task_id") or "") == task_id
        and str(row.get("candidate_sha") or "").lower() == candidate_sha.lower()
    ]


def resolve_authority(
    client: Any,
    *,
    supabase_url: str,
    service_role_key: str,
    workstream: str,
    task_id: str,
    candidate_sha: str,
    fencing_generation: int,
) -> AuthoritySnapshot:
    """Resolve exactly one current Runless V2 mutation authority and fail closed."""
    base = supabase_url.rstrip("/")
    headers = _headers(service_role_key)
    proofs = _read(
        client,
        base + "/rest/v1/proof_runs",
        headers,
        {
            "select": "proof_id,task_id,workstream,candidate_sha,fencing_generation,proof_fingerprint,state,scope_lease_id",
            "workstream": f"eq.{workstream}",
            "task_id": f"eq.{task_id}",
            "candidate_sha": f"eq.{candidate_sha}",
        },
    )
    # PostgREST applies these filters in production. Keep the same fail-closed
    # identity invariant locally so mocked/alternate clients cannot accidentally
    # authorize a row for a different task or candidate.
    proofs = _exact_proof_rows(
        proofs,
        workstream=workstream,
        task_id=task_id,
        candidate_sha=candidate_sha,
    )
    if not proofs:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_NOT_FOUND")
    if len(proofs) != 1:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_AMBIGUOUS")

    row = proofs[0]
    if int(row.get("fencing_generation") or -1) != int(fencing_generation):
        raise FinalizerAuthorityError("FINALIZER_STALE_FENCE")
    if str(row.get("state") or "") == "SUPERSEDED_BASE_DRIFT":
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_SUPERSEDED")

    leases = _read(
        client,
        base + "/rest/v1/workstream_leases",
        headers,
        {
            "select": "workstream,owner_proof_id,fencing_generation",
            "workstream": f"eq.{workstream}",
        },
    )
    leases = [lease for lease in leases if str(lease.get("workstream") or "") == workstream]
    if len(leases) != 1:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_AMBIGUOUS")
    lease = leases[0]
    if lease.get("owner_proof_id") != row.get("proof_id") or int(lease.get("fencing_generation") or -1) != int(fencing_generation):
        raise FinalizerAuthorityError("FINALIZER_STALE_FENCE")

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


def recover_terminal_authority(
    client: Any,
    *,
    supabase_url: str,
    service_role_key: str,
    workstream: str,
    task_id: str,
    candidate_sha: str,
    fencing_generation: int,
) -> RecoverySnapshot:
    """Recover one exact terminal proof identity without creating mutation authority.

    Recovery is deliberately read-only. It is valid only after the proof executor
    has released its short-lived workstream lease, and it never synthesizes a new
    proof, lease, gate, PR, branch, or candidate.
    """
    base = supabase_url.rstrip("/")
    headers = _headers(service_role_key)
    proofs = _read(
        client,
        base + "/rest/v1/proof_runs",
        headers,
        {
            "select": (
                "proof_id,task_id,workstream,candidate_sha,fencing_generation,"
                "proof_fingerprint,state,scope_lease_id,failure_class,detail"
            ),
            "workstream": f"eq.{workstream}",
            "task_id": f"eq.{task_id}",
            "candidate_sha": f"eq.{candidate_sha}",
        },
    )
    proofs = _exact_proof_rows(
        proofs,
        workstream=workstream,
        task_id=task_id,
        candidate_sha=candidate_sha,
    )
    if not proofs:
        raise FinalizerAuthorityError("FINALIZER_RECOVERY_NOT_FOUND")
    if len(proofs) != 1:
        raise FinalizerAuthorityError("FINALIZER_RECOVERY_AMBIGUOUS")

    row = proofs[0]
    if int(row.get("fencing_generation") or -1) != int(fencing_generation):
        raise FinalizerAuthorityError("FINALIZER_STALE_FENCE")

    state = str(row.get("state") or "")
    if state not in {"FAILED", "GREEN_FROZEN"}:
        raise FinalizerAuthorityError("FINALIZER_RECOVERY_NOT_TERMINAL")

    leases = _read(
        client,
        base + "/rest/v1/workstream_leases",
        headers,
        {
            "select": "workstream,owner_proof_id,fencing_generation",
            "workstream": f"eq.{workstream}",
        },
    )
    leases = [lease for lease in leases if str(lease.get("workstream") or "") == workstream]
    if leases:
        raise FinalizerAuthorityError("FINALIZER_RECOVERY_BUSY")

    return RecoverySnapshot(
        proof_id=str(row["proof_id"]),
        task_id=str(row["task_id"]),
        workstream=str(row["workstream"]),
        candidate_sha=str(row["candidate_sha"]),
        fencing_generation=int(row["fencing_generation"]),
        proof_fingerprint=str(row.get("proof_fingerprint") or ""),
        state=state,
        scope_lease_id=str(row.get("scope_lease_id") or ""),
        failure_class=str(row.get("failure_class") or ""),
        detail=str(row.get("detail") or ""),
        restart_required=False,
        next_legal_action=(
            "DIAGNOSE_EXISTING_TERMINAL_FAILURE" if state == "FAILED" else "NONE"
        ),
    )
