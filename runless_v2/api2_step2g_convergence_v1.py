"""API2 Step 2G — dual-main + Streamlit convergence contract.

Pure fail-closed validation. Network/GitHub/browser reads are performed by
separate API2-owned adapters; this module only decides whether 100% GREEN +
FROZEN is legally reportable.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

VERSION = "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1"
WHOLE_BRANCH_EQUALITY_REQUIRED = False
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_PROOF = re.compile(r"^sha256:[0-9a-f]{64}$")


class Step2GConvergenceFailure(RuntimeError):
    pass


def _identity(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise Step2GConvergenceFailure(f"STEP2G_{label.upper()}_REQUIRED")
    return text


def _sha(value: Any, label: str) -> str:
    text = _identity(value, label).lower()
    if not _SHA40.fullmatch(text):
        raise Step2GConvergenceFailure(f"STEP2G_{label.upper()}_INVALID")
    return text


def _proof(value: Any) -> str:
    text = _identity(value, "proof_digest").lower()
    if not _PROOF.fullmatch(text):
        raise Step2GConvergenceFailure("STEP2G_PROOF_DIGEST_INVALID")
    return text


def _artifact_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise Step2GConvergenceFailure("STEP2G_APPROVED_ARTIFACTS_REQUIRED")
    result: dict[str, str] = {}
    for path, blob in value.items():
        key = str(path or "").strip()
        if not key or key in result:
            raise Step2GConvergenceFailure("STEP2G_ARTIFACT_PATH_INVALID")
        result[key] = _sha(blob, "artifact_blob")
    return dict(sorted(result.items()))


def _require_branch_artifacts(
    evidence: Mapping[str, Any],
    *,
    field: str,
    branch: str,
    approved: Mapping[str, str],
    error: str,
) -> dict[str, Any]:
    raw = evidence.get(field)
    if not isinstance(raw, Mapping) or str(raw.get("branch") or "") != branch:
        raise Step2GConvergenceFailure(error)
    branch_sha = _sha(raw.get("sha"), f"{field}_sha")
    actual = raw.get("artifacts")
    if not isinstance(actual, Mapping):
        raise Step2GConvergenceFailure(error)
    mismatches = [
        path for path, expected in approved.items()
        if str(actual.get(path) or "").lower() != expected
    ]
    if mismatches:
        raise Step2GConvergenceFailure(error + ":" + ",".join(sorted(mismatches)))
    return {"branch": branch, "sha": branch_sha, "artifacts": dict(approved)}


def validate_convergence_evidence(
    evidence: Mapping[str, Any],
    *,
    production_url: str,
) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise Step2GConvergenceFailure("STEP2G_EVIDENCE_REQUIRED")
    if evidence.get("version") != VERSION:
        raise Step2GConvergenceFailure("STEP2G_VERSION_DRIFT")

    workstream = _identity(evidence.get("workstream"), "workstream")
    if not workstream.startswith("api2-"):
        raise Step2GConvergenceFailure("STEP2G_API2_WORKSTREAM_REQUIRED")
    freeze_token = _identity(evidence.get("freeze_token"), "freeze_token")
    candidate_sha = _sha(evidence.get("candidate_sha"), "candidate_sha")
    merged_main_sha = _sha(evidence.get("merged_main_sha"), "merged_main_sha")
    proof_digest = _proof(evidence.get("proof_digest"))
    approved = _artifact_map(evidence.get("approved_artifacts"))

    main = _require_branch_artifacts(
        evidence,
        field="main",
        branch="main",
        approved=approved,
        error="STEP2G_MAIN_ARTIFACT_DRIFT",
    )
    if main["sha"] != merged_main_sha:
        raise Step2GConvergenceFailure("STEP2G_MAIN_IDENTITY_DRIFT")
    api2_main = _require_branch_artifacts(
        evidence,
        field="api2_main",
        branch="api2-main",
        approved=approved,
        error="STEP2G_API2_MAIN_ARTIFACT_DRIFT",
    )

    streamlit = evidence.get("streamlit")
    if not isinstance(streamlit, Mapping):
        raise Step2GConvergenceFailure("STEP2G_STREAMLIT_EVIDENCE_REQUIRED")
    expected_url = str(production_url or "").strip().rstrip("/")
    if not expected_url.startswith("https://") or ".streamlit.app" not in expected_url:
        raise Step2GConvergenceFailure("STEP2G_PRODUCTION_URL_INVALID")
    if str(streamlit.get("url") or "").strip().rstrip("/") != expected_url:
        raise Step2GConvergenceFailure("STEP2G_STREAMLIT_TARGET_DRIFT")
    if streamlit.get("live_render_verified") is not True:
        raise Step2GConvergenceFailure("STEP2G_STREAMLIT_LIVE_RENDER_REQUIRED")

    required = [str(item) for item in (streamlit.get("required_markers") or []) if str(item)]
    observed = set(str(item) for item in (streamlit.get("observed_markers") or []) if str(item))
    if not required:
        raise Step2GConvergenceFailure("STEP2G_STREAMLIT_REQUIRED_MARKERS_EMPTY")
    missing = [marker for marker in required if marker not in observed]
    if missing:
        raise Step2GConvergenceFailure(
            "STEP2G_STREAMLIT_REQUIRED_MARKER_MISSING:" + ",".join(missing)
        )
    forbidden = [str(item) for item in (streamlit.get("forbidden_markers_present") or []) if str(item)]
    if forbidden:
        raise Step2GConvergenceFailure(
            "STEP2G_STREAMLIT_FORBIDDEN_MARKER:" + ",".join(forbidden)
        )
    body_sha = str(streamlit.get("body_sha256") or "").lower()
    if not _HASH64.fullmatch(body_sha):
        raise Step2GConvergenceFailure("STEP2G_STREAMLIT_BODY_DIGEST_INVALID")
    _identity(streamlit.get("observed_at_utc"), "streamlit_observed_at_utc")

    return {
        "status": "GREEN",
        "version": VERSION,
        "step2g_green": True,
        "green_frozen_allowed": True,
        "completion_percent": 100.0,
        "whole_branch_equality_required": WHOLE_BRANCH_EQUALITY_REQUIRED,
        "feature_scoped_artifact_parity": True,
        "workstream": workstream,
        "freeze_token": freeze_token,
        "candidate_sha": candidate_sha,
        "merged_main_sha": merged_main_sha,
        "proof_digest": proof_digest,
        "main_sha": main["sha"],
        "api2_main_sha": api2_main["sha"],
        "production_url": expected_url,
    }


def require_step2g_closeout(
    evidence: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    production_url: str,
) -> dict[str, Any]:
    required_identity = {
        "workstream": _identity(expected.get("workstream"), "expected_workstream"),
        "freeze_token": _identity(expected.get("freeze_token"), "expected_freeze_token"),
        "candidate_sha": _sha(expected.get("candidate_sha"), "expected_candidate_sha"),
        "merged_main_sha": _sha(expected.get("merged_main_sha"), "expected_merged_main_sha"),
        "proof_digest": _proof(expected.get("proof_digest")),
        "approved_artifacts": _artifact_map(expected.get("approved_artifacts")),
    }
    actual_identity = {
        "workstream": str(evidence.get("workstream") or ""),
        "freeze_token": str(evidence.get("freeze_token") or ""),
        "candidate_sha": str(evidence.get("candidate_sha") or "").lower(),
        "merged_main_sha": str(evidence.get("merged_main_sha") or "").lower(),
        "proof_digest": str(evidence.get("proof_digest") or "").lower(),
        "approved_artifacts": _artifact_map(evidence.get("approved_artifacts")),
    }
    if actual_identity != required_identity:
        raise Step2GConvergenceFailure("STEP2G_SIDECAR_IDENTITY_DRIFT")
    return validate_convergence_evidence(evidence, production_url=production_url)
