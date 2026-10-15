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
    """Resolve exactly one current Runless V2 authority row and fail closed."""
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
    proofs = [
        row
        for row in proofs
        if str(row.get("workstream") or "") == workstream
        and str(row.get("task_id") or "") == task_id
        and str(row.get("candidate_sha") or "").lower() == candidate_sha.lower()
    ]
    if not proofs:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_NOT_FOUND")
    if len(proofs) != 1:
        raise FinalizerAuthorityError("FINALIZER_AUTHORITY_AMBIGUOUS")

    row = proofs[0]
    if int(row.get("fencing_generation") or -1) != int(fencing_generation):
        raise FinalizerAuthorityError("FINALIZER_STALE_FENCE")

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
