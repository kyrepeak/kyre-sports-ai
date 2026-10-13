from __future__ import annotations

import hashlib
from typing import Any

import httpx

from .config import Settings
from .models import FailureClass, LeaseClaim, ProofRequest, ProofState, ProofStatus


class RunlessV2StateError(RuntimeError):
    pass


class WorkstreamBusy(RunlessV2StateError):
    pass


class AuthorityConflict(RunlessV2StateError):
    pass


class StaleFence(RunlessV2StateError):
    pass


class IllegalTransition(RunlessV2StateError):
    pass


_ERROR_MAP = {
    "RUNLESS_V2_WORKSTREAM_BUSY": WorkstreamBusy,
    "RUNLESS_V2_AUTHORITY_CONFLICT": AuthorityConflict,
    "RUNLESS_V2_STALE_FENCE": StaleFence,
    "RUNLESS_V2_ILLEGAL_TRANSITION": IllegalTransition,
}


class DurableStateStore:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=20)

    @property
    def _headers(self) -> dict[str, str]:
        key = self.settings.supabase_service_role_key
        headers = {
            "apikey": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if not key.startswith(("sb_secret_", "sb_publishable_")):
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _url(self, path: str) -> str:
        return self.settings.supabase_url.rstrip("/") + path

    def health(self) -> bool:
        response = self.client.get(
            self._url("/rest/v1/proof_runs"),
            headers=self._headers,
            params={"select": "proof_id", "limit": "1"},
        )
        return response.status_code < 400

    def _raise(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        detail = str(payload.get("message") or payload.get("detail") or payload.get("code") or response.text)
        for marker, exc_type in _ERROR_MAP.items():
            if marker in detail:
                raise exc_type(marker)
        raise RunlessV2StateError(detail or f"RUNLESS_V2_HTTP_{response.status_code}")

    def _rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = self.client.post(
            self._url(f"/rest/v1/rpc/{name}"), headers=self._headers, json=payload
        )
        if response.status_code >= 400:
            self._raise(response)
        return response.json()

    @staticmethod
    def _single(payload: Any) -> dict[str, Any]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RunlessV2StateError("RUNLESS_V2_EXPECTED_SINGLE_ROW")
            return dict(payload[0])
        if isinstance(payload, dict):
            return dict(payload)
        raise RunlessV2StateError("RUNLESS_V2_BAD_RESPONSE")

    def claim(
        self,
        request: ProofRequest,
        request_fingerprint: str,
        ttl_seconds: int,
        *,
        proof_id: str,
    ) -> LeaseClaim:
        row = self._single(
            self._rpc(
                "claim_workstream",
                {
                    "p_workstream": request.workstream,
                    "p_proof_id": proof_id,
                    "p_task_id": request.task_id,
                    "p_candidate_sha": request.candidate_sha,
                    "p_expected_main_sha": request.expected_main_sha,
                    "p_scope_lease_id": request.lease_id,
                    "p_authorization_id": request.authorization_id,
                    "p_request_fingerprint": request_fingerprint,
                    "p_ttl_seconds": ttl_seconds,
                },
            )
        )
        return LeaseClaim(workstream=request.workstream, **row)

    def renew(self, claim: LeaseClaim, ttl_seconds: int) -> LeaseClaim:
        row = self._single(
            self._rpc(
                "renew_workstream",
                {
                    "p_workstream": claim.workstream,
                    "p_proof_id": claim.proof_id,
                    "p_lease_token": claim.lease_token,
                    "p_fencing_generation": claim.fencing_generation,
                    "p_ttl_seconds": ttl_seconds,
                },
            )
        )
        return LeaseClaim(
            proof_id=claim.proof_id,
            workstream=claim.workstream,
            state=claim.state,
            reused=True,
            **row,
        )

    def advance(
        self,
        proof_id: str,
        expected: ProofState,
        target: ProofState,
        claim: LeaseClaim,
        detail: str = "",
    ) -> ProofStatus:
        row = self._single(
            self._rpc(
                "advance_proof_state",
                {
                    "p_proof_id": proof_id,
                    "p_expected_state": expected.value,
                    "p_target_state": target.value,
                    "p_lease_token": claim.lease_token,
                    "p_fencing_generation": claim.fencing_generation,
                    "p_detail": detail,
                },
            )
        )
        return ProofStatus(**row)

    @staticmethod
    def _detail_digest(detail: str) -> str:
        return hashlib.sha256(detail.encode("utf-8")).hexdigest()

    def record_failure_and_release(
        self,
        claim: LeaseClaim,
        *,
        failure_class: FailureClass,
        detail: str,
        record_fingerprint: bool = True,
    ) -> ProofStatus:
        row = self._single(
            self._rpc(
                "record_failure_and_release",
                {
                    "p_proof_id": claim.proof_id,
                    "p_lease_token": claim.lease_token,
                    "p_fencing_generation": claim.fencing_generation,
                    "p_failure_class": failure_class.value,
                    "p_detail": detail,
                    "p_detail_digest": self._detail_digest(detail),
                    "p_record_fingerprint": record_fingerprint,
                },
            )
        )
        return ProofStatus(**row)

    def release_infra(self, claim: LeaseClaim, *, detail: str) -> ProofStatus:
        return self.record_failure_and_release(
            claim, failure_class=FailureClass.INFRA, detail=detail, record_fingerprint=False
        )

    def record_merge_authorized_and_release_execution(
        self,
        claim: LeaseClaim,
        *,
        proof_fingerprint: str,
        receipt_digest: str,
        gate_check_run_id: int,
        receipt_json: dict[str, Any],
        github_receipt_ref: str,
        github_receipt_path: str,
    ) -> ProofStatus:
        row = self._single(
            self._rpc(
                "record_merge_authorized_and_release_execution",
                {
                    "p_proof_id": claim.proof_id,
                    "p_lease_token": claim.lease_token,
                    "p_fencing_generation": claim.fencing_generation,
                    "p_proof_fingerprint": proof_fingerprint,
                    "p_receipt_digest": receipt_digest,
                    "p_gate_check_run_id": gate_check_run_id,
                    "p_receipt_json": receipt_json,
                    "p_github_receipt_ref": github_receipt_ref,
                    "p_github_receipt_path": github_receipt_path,
                },
            )
        )
        return ProofStatus(**row)

    def status(self, proof_id: str) -> ProofStatus:
        response = self.client.get(
            self._url("/rest/v1/proof_runs"),
            headers=self._headers,
            params={"select": "*", "proof_id": f"eq.{proof_id}", "limit": "1"},
        )
        if response.status_code >= 400:
            self._raise(response)
        return ProofStatus(**self._single(response.json()))

    def receipt_mirror(self, proof_id: str) -> dict[str, Any]:
        response = self.client.get(
            self._url("/rest/v1/receipt_mirrors"),
            headers=self._headers,
            params={"select": "*", "proof_id": f"eq.{proof_id}", "limit": "1"},
        )
        if response.status_code >= 400:
            self._raise(response)
        return self._single(response.json())

    def closeout_green_frozen(
        self,
        proof_id: str,
        *,
        candidate_sha: str,
        merged_main_sha: str,
        freeze_token: str,
        proof_digest: str,
        manifest_state_hash: str,
    ) -> ProofStatus:
        row = self._single(
            self._rpc(
                "closeout_green_frozen",
                {
                    "p_proof_id": proof_id,
                    "p_candidate_sha": candidate_sha,
                    "p_merged_main_sha": merged_main_sha,
                    "p_freeze_token": freeze_token,
                    "p_proof_digest": proof_digest,
                    "p_manifest_state_hash": manifest_state_hash,
                },
            )
        )
        return ProofStatus(**row)
