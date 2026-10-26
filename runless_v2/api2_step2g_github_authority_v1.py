"""API2 Step 2G GitHub readback adapter.

Adds API2-only dual-branch artifact readback plus canonical Streamlit target
resolution without replacing legacy/non-API2 authority behavior.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from typing import Any, Mapping
from urllib.parse import quote

from . import github_authority as _gha

VERSION = "API2_STEP2G_GITHUB_AUTHORITY_V1"
STEP2G_MARKER = "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1"
EVIDENCE_BRANCH = "api2-step2g-convergence-evidence"
EVIDENCE_DIR = "devsystem/step2g_convergence_evidence"
PRODUCTION_TARGETS_PATH = "devsystem/production_targets_v1.json"
INTEGRATION_MARKERS: dict[str, tuple[str, ...]] = {
    "app.py": (STEP2G_MARKER,),
    "runless_v2/app.py": (
        "api2_step2g_github_authority_v1",
        "api2_step2g_closeout_enforcement_v1",
    ),
}


def _branch_sha(self, branch: str) -> str:
    raw = self._request("GET", f"/git/ref/heads/{quote(branch, safe='')}")
    return str(((raw or {}).get("object") or {}).get("sha") or "").lower()


def _content_text(self, path: str, branch: str) -> str:
    raw = self._request("GET", f"/contents/{quote(path, safe='/')}?ref={quote(branch, safe='')}")
    if not isinstance(raw, Mapping) or raw.get("encoding") != "base64":
        raise _gha.GithubAuthorityError(f"RUNLESS_V2_STEP2G_BRANCH_INTEGRATION_READ_FAILED:{branch}:{path}")
    try:
        return base64.b64decode(str(raw.get("content") or "")).decode("utf-8")
    except Exception as exc:
        raise _gha.GithubAuthorityError(f"RUNLESS_V2_STEP2G_BRANCH_INTEGRATION_DECODE_FAILED:{branch}:{path}") from exc


def _verify_branch_integration(self, branch: str) -> dict[str, Any]:
    verified: dict[str, list[str]] = {}
    for path, markers in INTEGRATION_MARKERS.items():
        source = _content_text(self, path, branch)
        missing = [marker for marker in markers if marker not in source]
        if missing:
            raise _gha.GithubAuthorityError(
                "RUNLESS_V2_STEP2G_BRANCH_INTEGRATION_MARKER_MISSING:"
                + branch + ":" + path + ":" + ",".join(missing)
            )
        verified[path] = list(markers)
    return {"branch": branch, "verified": verified}


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
    evidence["main"] = {"branch": "main", "sha": main_sha, "artifacts": {path: str(main_tree.get(path) or "").lower() for path in paths}}
    evidence["api2_main"] = {"branch": "api2-main", "sha": api2_main_sha, "artifacts": {path: str(api2_tree.get(path) or "").lower() for path in paths}}
    evidence["branch_integration"] = {
        "main": _verify_branch_integration(self, "main"),
        "api2_main": _verify_branch_integration(self, "api2-main"),
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
