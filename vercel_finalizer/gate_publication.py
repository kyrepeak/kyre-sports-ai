from __future__ import annotations

from dataclasses import dataclass
from typing import Any

APP_ID_EXPECTED = "5204253"
GATE_NAME = "runless-final-gate"


class GatePublicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GateClaimDecision:
    publish: bool
    reused: bool
    claim_token: str | None = None
    gate_check_run_id: int | None = None


def _receipt_token(proof_digest: str) -> str:
    value = str(proof_digest or "").strip().lower()
    if value.startswith("sha256:"):
        value = value[7:]
    return value


def _matches_gate(
    check: dict[str, Any],
    *,
    candidate_sha: str,
    proof_digest: str,
    proof_id: str,
    gate_name: str = GATE_NAME,
    app_id: str = APP_ID_EXPECTED,
) -> bool:
    summary = str((check.get("output") or {}).get("summary") or "")
    return (
        check.get("name") == gate_name
        and check.get("status") == "completed"
        and check.get("conclusion") == "success"
        and str(check.get("head_sha") or "").lower() == candidate_sha.lower()
        and str((check.get("app") or {}).get("id")) == str(app_id)
        and f"receipt={_receipt_token(proof_digest)}" in summary
        and f"proof={proof_id}" in summary
    )


def find_exact_gate(
    checks: list[dict[str, Any]],
    *,
    candidate_sha: str,
    proof_digest: str,
    proof_id: str,
    expected_check_run_id: int | None = None,
    gate_name: str = GATE_NAME,
    app_id: str = APP_ID_EXPECTED,
) -> dict[str, Any] | None:
    named = [check for check in checks if check.get("name") == gate_name]
    relevant = list(named)
    if expected_check_run_id is not None:
        relevant = [check for check in relevant if int(check.get("id") or 0) == int(expected_check_run_id)]
    for check in relevant:
        if _matches_gate(
            check,
            candidate_sha=candidate_sha,
            proof_digest=proof_digest,
            proof_id=proof_id,
            gate_name=gate_name,
            app_id=app_id,
        ):
            return check
    if named:
        raise GatePublicationError("FINALIZER_GATE_IDENTITY_MISMATCH")
    return None


def exact_gate_check(
    checks: list[dict[str, Any]],
    *,
    candidate_sha: str,
    proof_digest: str,
    proof_id: str,
    expected_check_run_id: int | None = None,
) -> dict[str, Any]:
    found = find_exact_gate(
        checks,
        candidate_sha=candidate_sha,
        proof_digest=proof_digest,
        proof_id=proof_id,
        expected_check_run_id=expected_check_run_id,
    )
    if found is None:
        raise GatePublicationError("FINALIZER_GATE_READBACK_FAILED")
    return found


def project_claim_result(payload: dict[str, Any]) -> GateClaimDecision:
    decision = str(payload.get("decision") or "").upper()
    if decision == "CLAIMED":
        token = str(payload.get("claim_token") or "")
        if not token:
            raise GatePublicationError("FINALIZER_GATE_CLAIM_INVALID")
        return GateClaimDecision(publish=True, reused=False, claim_token=token)
    if decision == "EXISTING":
        check_id = int(payload.get("gate_check_run_id") or 0)
        if check_id <= 0:
            raise GatePublicationError("FINALIZER_GATE_CLAIM_INVALID")
        return GateClaimDecision(publish=False, reused=True, gate_check_run_id=check_id)
    if decision == "IN_PROGRESS":
        raise GatePublicationError("FINALIZER_GATE_PUBLICATION_IN_PROGRESS")
    raise GatePublicationError("FINALIZER_GATE_CLAIM_INVALID")


def _supabase_headers(service_role_key: str) -> dict[str, str]:
    headers = {
        "apikey": service_role_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Profile": "runless_v2",
    }
    if not service_role_key.startswith(("sb_secret_", "sb_publishable_")):
        headers["Authorization"] = f"Bearer {service_role_key}"
    return headers


def _rpc(client: Any, *, supabase_url: str, service_role_key: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        supabase_url.rstrip("/") + f"/rest/v1/rpc/{name}",
        headers=_supabase_headers(service_role_key),
        json=payload,
    )
    if response.status_code >= 400:
        raise GatePublicationError("FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE")
    try:
        body = response.json()
    except Exception as exc:
        raise GatePublicationError("FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE") from exc
    if isinstance(body, list):
        if len(body) != 1 or not isinstance(body[0], dict):
            raise GatePublicationError("FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE")
        body = body[0]
    if not isinstance(body, dict):
        raise GatePublicationError("FINALIZER_GATE_CLAIM_STORE_UNAVAILABLE")
    return dict(body)


def claim_publication(
    client: Any,
    *,
    supabase_url: str,
    service_role_key: str,
    proof_id: str,
    candidate_sha: str,
    fencing_generation: int,
    proof_digest: str,
    claim_token: str,
) -> GateClaimDecision:
    payload = _rpc(
        client,
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        name="claim_final_gate_publication",
        payload={
            "p_proof_id": proof_id,
            "p_candidate_sha": candidate_sha,
            "p_fencing_generation": int(fencing_generation),
            "p_proof_digest": proof_digest,
            "p_claim_token": claim_token,
        },
    )
    return project_claim_result(payload)


def complete_publication(
    client: Any,
    *,
    supabase_url: str,
    service_role_key: str,
    proof_id: str,
    claim_token: str,
    gate_check_run_id: int,
) -> int:
    payload = _rpc(
        client,
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        name="complete_final_gate_publication",
        payload={
            "p_proof_id": proof_id,
            "p_claim_token": claim_token,
            "p_gate_check_run_id": int(gate_check_run_id),
        },
    )
    check_id = int(payload.get("gate_check_run_id") or 0)
    if check_id <= 0:
        raise GatePublicationError("FINALIZER_GATE_COMPLETION_INVALID")
    return check_id
