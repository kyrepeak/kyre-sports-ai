"""MONSTER-owned runtime identity for Step 2G live convergence proof."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "MONSTER_STEP2G_RUNTIME_IDENTITY_V1"
ROUTER_OWNER = "MONSTER_CANONICAL_ROUTER"
ENTRYPOINT = "app.py"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _require_sha(value: str, label: str) -> str:
    value = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(value):
        raise RuntimeError(f"{label} is not an exact git SHA")
    return value


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    )
    return completed.stdout.strip()


def artifact_digest_from_tree(tree_sha: str) -> str:
    tree_sha = _require_sha(tree_sha, "tree SHA")
    return hashlib.sha256(tree_sha.encode("ascii")).hexdigest()


def build_runtime_identity(*, sha: str, tree_sha: str, deployment_id: str) -> dict[str, Any]:
    sha = _require_sha(sha, "runtime SHA")
    tree_sha = _require_sha(tree_sha, "runtime tree SHA")
    deployment_id = str(deployment_id or "").strip()
    if not deployment_id:
        raise RuntimeError("MONSTER deployment identity is required")
    return {
        "owner": "MONSTER",
        "sha": sha,
        "tree_sha": tree_sha,
        "artifact_digest": artifact_digest_from_tree(tree_sha),
        "deployment_id": deployment_id,
        "entrypoint": ENTRYPOINT,
        "router_owner": ROUTER_OWNER,
        "schema_version": SCHEMA_VERSION,
    }


def resolve_runtime_identity(repo_root: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or Path(__file__).resolve().parents[1])
    sha = _require_sha(_git(root, "rev-parse", "HEAD"), "runtime SHA")
    tree_sha = _require_sha(_git(root, "rev-parse", "HEAD^{tree}"), "runtime tree SHA")
    deployment_id = os.environ.get("MONSTER_DEPLOYMENT_ID", "").strip() or f"monster-streamlit-{sha[:12]}"
    return build_runtime_identity(sha=sha, tree_sha=tree_sha, deployment_id=deployment_id)


def runtime_identity_marker_html(identity: dict[str, Any]) -> str:
    payload = html.escape(json.dumps(identity, sort_keys=True, separators=(",", ":")), quote=True)
    return (
        '<div id="monster-runtime-identity" '
        f'data-monster-runtime-identity="{payload}" '
        'style="display:none" aria-hidden="true"></div>'
    )


def unescape_marker_payload(payload: str) -> str:
    return html.unescape(payload)


def emit_runtime_identity_marker() -> dict[str, Any]:
    identity = resolve_runtime_identity()
    import streamlit as st
    st.markdown(runtime_identity_marker_html(identity), unsafe_allow_html=True)
    return identity


if __name__ == "__main__":
    print(json.dumps(resolve_runtime_identity(), sort_keys=True))
