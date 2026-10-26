"""MONSTER-owned runtime identity for Step 2G live convergence proof.

The certified MONSTER control-plane identity is intentionally distinct from the
shared production runtime identity. Production may execute from protected
``main`` while the certified MONSTER state lives on ``monster-main``; Step 2G
must prove both identities instead of pretending their commit SHAs are equal.
"""
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
CERTIFICATION_SCHEMA = "MONSTER_STEP2G_RUNTIME_CERTIFICATION_V1"
CERTIFICATION_PATH = "devsystem/monster_runtime_certification_v1.json"
ROUTER_OWNER = "MONSTER_CANONICAL_ROUTER"
ENTRYPOINT = "app.py"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _require_sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise RuntimeError(f"{label} is not an exact git SHA")
    return text


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


def build_runtime_identity(
    *,
    deployment_id: str,
    sha: str | None = None,
    tree_sha: str | None = None,
    certified_sha: str | None = None,
    certified_tree_sha: str | None = None,
    runtime_sha: str | None = None,
    runtime_tree_sha: str | None = None,
) -> dict[str, Any]:
    """Build one MONSTER identity packet with backwards-compatible aliases.

    ``sha``/``tree_sha`` are the original V1 parameters. If the split identity
    parameters are absent they are used for both certified and runtime identity.
    """
    legacy_sha = _require_sha(sha, "runtime SHA") if sha is not None else None
    legacy_tree = _require_sha(tree_sha, "runtime tree SHA") if tree_sha is not None else None

    certified = _require_sha(
        certified_sha if certified_sha is not None else legacy_sha,
        "certified MONSTER SHA",
    )
    certified_tree = _require_sha(
        certified_tree_sha if certified_tree_sha is not None else legacy_tree,
        "certified MONSTER tree SHA",
    )
    runtime = _require_sha(
        runtime_sha if runtime_sha is not None else legacy_sha or certified,
        "production runtime SHA",
    )
    runtime_tree = _require_sha(
        runtime_tree_sha if runtime_tree_sha is not None else legacy_tree or certified_tree,
        "production runtime tree SHA",
    )

    deployment_id = str(deployment_id or "").strip()
    if not deployment_id:
        raise RuntimeError("MONSTER deployment identity is required")

    certified_digest = artifact_digest_from_tree(certified_tree)
    runtime_digest = artifact_digest_from_tree(runtime_tree)
    return {
        "owner": "MONSTER",
        "sha": certified,
        "tree_sha": certified_tree,
        "artifact_digest": certified_digest,
        "certified_monster_sha": certified,
        "certified_monster_tree_sha": certified_tree,
        "certified_artifact_digest": certified_digest,
        "runtime_sha": runtime,
        "runtime_tree_sha": runtime_tree,
        "runtime_artifact_digest": runtime_digest,
        "deployment_id": deployment_id,
        "entrypoint": ENTRYPOINT,
        "router_owner": ROUTER_OWNER,
        "schema_version": SCHEMA_VERSION,
    }


def _read_certification(root: Path, runtime_sha: str, runtime_tree_sha: str) -> tuple[str, str]:
    path = root / CERTIFICATION_PATH
    if not path.is_file():
        return runtime_sha, runtime_tree_sha
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("MONSTER runtime certification descriptor is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != CERTIFICATION_SCHEMA:
        raise RuntimeError("MONSTER runtime certification descriptor schema mismatch")
    if payload.get("authority") != "MONSTER_ONLY":
        raise RuntimeError("MONSTER runtime certification descriptor authority mismatch")
    return (
        _require_sha(payload.get("certified_monster_sha"), "certified MONSTER SHA"),
        _require_sha(payload.get("certified_monster_tree_sha"), "certified MONSTER tree SHA"),
    )


def resolve_runtime_identity(repo_root: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or Path(__file__).resolve().parents[1])
    runtime_sha = _require_sha(_git(root, "rev-parse", "HEAD"), "production runtime SHA")
    runtime_tree_sha = _require_sha(_git(root, "rev-parse", "HEAD^{tree}"), "production runtime tree SHA")
    certified_sha, certified_tree_sha = _read_certification(root, runtime_sha, runtime_tree_sha)
    deployment_id = os.environ.get("MONSTER_DEPLOYMENT_ID", "").strip() or f"monster-streamlit-{runtime_sha[:12]}"
    return build_runtime_identity(
        certified_sha=certified_sha,
        certified_tree_sha=certified_tree_sha,
        runtime_sha=runtime_sha,
        runtime_tree_sha=runtime_tree_sha,
        deployment_id=deployment_id,
    )


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
