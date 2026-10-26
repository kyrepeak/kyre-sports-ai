"""API2 Step 2G GitHub readback adapter.

Adds API2-only dual-branch artifact readback plus canonical Streamlit target
resolution without replacing legacy/non-API2 authority behavior.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from urllib.parse import quote

from . import github_authority as _gha

VERSION = "API2_STEP2G_GITHUB_AUTHORITY_V1"
EVIDENCE_BRANCH = "api2-step2g-convergence-evidence"
EVIDENCE_DIR = "devsystem/step2g_convergence_evidence"
PRODUCTION_TARGETS_PATH = "devsystem/production_targets_v1.json"


def _branch_sha(self, branch: str) -> str:
    raw = self._request("GET", f"/git/ref/heads/{quote(branch, safe='')}")
    return str(((raw or {}).get("object") or {}).get("sha") or "").lower()


def _read_step2g_convergence_evidence(self, freeze_token: str) -> dict[str, Any]:
    token = str(freeze_token or "").strip()
    if not token.startswith("API2_"):
        raise _gha.GithubAuthorityError("RUNLESS_V2_STEP2G_API2_FREEZE_TOKEN_REQUIRED")

    path = f"{EVIDENCE_DIR}/{token}.json"
    sidecar = self._content_json(path, EVIDENCE_BRANCH)
    if not isinstance(sidecar, Mapping):
        raise _gha.GithubAuthorityError("RUNLESS_V2_STEP2G_EVIDENCE_INVALID")
    evidence = deepcopy(dict(sidecar))
    approved = evidence.get("approved_artifacts")
    if not isinstance(approved, Mapping) or not approved:
        raise _gha.GithubAuthorityError("RUNLESS_V2_STEP2G_APPROVED_ARTIFACTS_REQUIRED")

    main_sha = _branch_sha(self, "main")
    api2_main_sha = _branch_sha(self, "api2-main")
    if not main_sha or not api2_main_sha:
        raise _gha.GithubAuthorityError("RUNLESS_V2_STEP2G_BRANCH_IDENTITY_UNAVAILABLE")
    main_tree = self.tree_blobs(main_sha)
    api2_tree = self.tree_blobs(api2_main_sha)
    paths = [str(path) for path in approved]
    evidence["main"] = {
        "branch": "main",
        "sha": main_sha,
        "artifacts": {path: str(main_tree.get(path) or "").lower() for path in paths},
    }
    evidence["api2_main"] = {
        "branch": "api2-main",
        "sha": api2_main_sha,
        "artifacts": {path: str(api2_tree.get(path) or "").lower() for path in paths},
    }

    targets = self._content_json(PRODUCTION_TARGETS_PATH, "main")
    streamlit = (targets or {}).get("streamlit") if isinstance(targets, Mapping) else None
    production_url = str((streamlit or {}).get("url") or "").strip().rstrip("/")
    if not production_url.startswith("https://") or ".streamlit.app" not in production_url:
        raise _gha.GithubAuthorityError("RUNLESS_V2_STEP2G_PRODUCTION_TARGET_INVALID")
    evidence["canonical_production_url"] = production_url
    evidence["authority_version"] = VERSION
    return evidence


_gha.STEP2G_EVIDENCE_BRANCH = EVIDENCE_BRANCH
_gha.STEP2G_EVIDENCE_DIR = EVIDENCE_DIR
_gha.GithubAuthority.read_step2g_convergence_evidence = _read_step2g_convergence_evidence
