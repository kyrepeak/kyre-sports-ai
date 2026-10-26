"""Permanent API2 Step 2G enforcement on durable GREEN_FROZEN closeout.

This additive wrapper preserves all non-API2 closeout behavior. API2 workstreams
must provide dual-main + Streamlit convergence evidence before the original
DurableStateStore closeout transition is allowed to run.
"""
from __future__ import annotations

from typing import Any

from .api2_step2g_convergence_v1 import Step2GConvergenceFailure, require_step2g_closeout
from .github_authority import GithubAuthority, GithubAuthorityError
from .state_store import DurableStateStore, RunlessV2StateError

VERSION = "API2_STEP2G_CLOSEOUT_ENFORCEMENT_V1"


def require_api2_step2g_closeout(
    store: DurableStateStore,
    *,
    proof_id: str,
    candidate_sha: str,
    merged_main_sha: str,
    freeze_token: str,
    proof_digest: str,
) -> dict[str, Any] | None:
    status = store.status(proof_id)
    workstream = str(status.workstream or "")
    if not workstream.startswith("api2-"):
        return None

    try:
        mirror = store.receipt_mirror(proof_id)
        receipt = mirror.get("receipt_json") if isinstance(mirror, dict) else None
        if not isinstance(receipt, dict):
            raise Step2GConvergenceFailure("STEP2G_RECEIPT_REQUIRED")
        approved_artifacts = receipt.get("artifact_map")
        gh = GithubAuthority(store.settings)
        evidence = gh.read_step2g_convergence_evidence(freeze_token)
        production_url = str(evidence.get("canonical_production_url") or "")
        return require_step2g_closeout(
            evidence,
            expected={
                "workstream": workstream,
                "freeze_token": freeze_token,
                "candidate_sha": candidate_sha,
                "merged_main_sha": merged_main_sha,
                "proof_digest": proof_digest,
                "approved_artifacts": approved_artifacts,
            },
            production_url=production_url,
        )
    except (Step2GConvergenceFailure, GithubAuthorityError) as exc:
        raise RunlessV2StateError("RUNLESS_V2_STEP2G_BLOCKED:" + str(exc)) from exc


def _install() -> None:
    if hasattr(DurableStateStore, "_api2_step2g_original_closeout_green_frozen"):
        return
    original = DurableStateStore.closeout_green_frozen
    DurableStateStore._api2_step2g_original_closeout_green_frozen = original  # type: ignore[attr-defined]

    def closeout_green_frozen_with_step2g(
        self: DurableStateStore,
        proof_id: str,
        *,
        candidate_sha: str,
        merged_main_sha: str,
        freeze_token: str,
        proof_digest: str,
        manifest_state_hash: str,
    ):
        require_api2_step2g_closeout(
            self,
            proof_id=proof_id,
            candidate_sha=candidate_sha,
            merged_main_sha=merged_main_sha,
            freeze_token=freeze_token,
            proof_digest=proof_digest,
        )
        return original(
            self,
            proof_id,
            candidate_sha=candidate_sha,
            merged_main_sha=merged_main_sha,
            freeze_token=freeze_token,
            proof_digest=proof_digest,
            manifest_state_hash=manifest_state_hash,
        )

    DurableStateStore.closeout_green_frozen = closeout_green_frozen_with_step2g  # type: ignore[assignment]


_install()
