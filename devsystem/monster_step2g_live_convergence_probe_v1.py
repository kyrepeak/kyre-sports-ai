"""Live MONSTER Step 2G production convergence probe.

Runs only as MONSTER supporting evidence. It proves two independent identities:
(1) the exact certified MONSTER state and (2) the actual protected shared-main
runtime executing behind the stable Streamlit alias.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "MONSTER_STEP2G_LIVE_CONVERGENCE_PROOF_V1"
RUNTIME_SCHEMA = "MONSTER_STEP2G_RUNTIME_IDENTITY_V1"
ROUTER_OWNER = "MONSTER_CANONICAL_ROUTER"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _artifact_digest(tree_sha: str) -> str:
    return hashlib.sha256(tree_sha.lower().encode("ascii")).hexdigest()


def expected_identity(
    certified_sha: str,
    certified_tree_sha: str,
    runtime_sha: str,
    runtime_tree_sha: str,
) -> dict[str, str]:
    certified_sha = certified_sha.lower()
    certified_tree_sha = certified_tree_sha.lower()
    runtime_sha = runtime_sha.lower()
    runtime_tree_sha = runtime_tree_sha.lower()
    certified_digest = _artifact_digest(certified_tree_sha)
    runtime_digest = _artifact_digest(runtime_tree_sha)
    return {
        "owner": "MONSTER",
        "sha": certified_sha,
        "tree_sha": certified_tree_sha,
        "artifact_digest": certified_digest,
        "certified_monster_sha": certified_sha,
        "certified_monster_tree_sha": certified_tree_sha,
        "certified_artifact_digest": certified_digest,
        "runtime_sha": runtime_sha,
        "runtime_tree_sha": runtime_tree_sha,
        "runtime_artifact_digest": runtime_digest,
        "deployment_id": f"monster-streamlit-{runtime_sha[:12]}",
        "entrypoint": "app.py",
        "router_owner": ROUTER_OWNER,
        "schema_version": RUNTIME_SCHEMA,
    }


def probe(
    *,
    url: str,
    expected_sha: str,
    expected_tree_sha: str,
    expected_runtime_sha: str,
    expected_runtime_tree_sha: str,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        if response is None or response.status >= 400:
            raise RuntimeError("MONSTER stable production alias did not load successfully")
        health_status = response.status
        health_body = "stable production alias root loaded"
        final_url = page.url
        marker = page.locator("#monster-runtime-identity")
        marker.wait_for(state="attached", timeout=120_000)
        encoded = marker.get_attribute("data-monster-runtime-identity")
        if not encoded:
            raise RuntimeError("MONSTER runtime identity marker is missing payload")
        live_identity = json.loads(html.unescape(encoded))
        body_text = page.locator("body").inner_text(timeout=30_000)
        browser.close()

    expected = expected_identity(
        expected_sha,
        expected_tree_sha,
        expected_runtime_sha,
        expected_runtime_tree_sha,
    )

    certified_keys = (
        "owner",
        "sha",
        "tree_sha",
        "artifact_digest",
        "certified_monster_sha",
        "certified_monster_tree_sha",
        "certified_artifact_digest",
        "entrypoint",
        "router_owner",
        "schema_version",
    )
    certified_mismatch = {
        key: {"actual": live_identity.get(key), "expected": expected.get(key)}
        for key in certified_keys
        if live_identity.get(key) != expected.get(key)
    }
    if certified_mismatch:
        raise RuntimeError(f"PRODUCTION_NOT_UPDATED: certified MONSTER identity mismatch {certified_mismatch!r}")

    runtime_keys = ("runtime_sha", "runtime_tree_sha", "runtime_artifact_digest", "deployment_id")
    runtime_mismatch = {
        key: {"actual": live_identity.get(key), "expected": expected.get(key)}
        for key in runtime_keys
        if live_identity.get(key) != expected.get(key)
    }
    if runtime_mismatch:
        raise RuntimeError(f"PRODUCTION_RUNTIME_MISMATCH: {runtime_mismatch!r}")

    lowered = body_text.lower()
    if not body_text.strip() or "encountered an error" in lowered or "traceback" in lowered:
        raise RuntimeError("USER_FACING_PARITY_FAILURE: production body is blank or errored")

    proof = {
        "schema_version": SCHEMA_VERSION,
        "authority": "MONSTER_ONLY",
        "stable_alias": url.rstrip("/"),
        "health": {
            "status": health_status,
            "body": health_body,
            "transport": "chromium_root",
            "final_url": final_url,
        },
        "certified_monster_identity": {
            "sha": expected_sha.lower(),
            "tree_sha": expected_tree_sha.lower(),
            "artifact_digest": _artifact_digest(expected_tree_sha),
        },
        "runtime_identity": live_identity,
        "production_runtime": {
            "sha": expected_runtime_sha.lower(),
            "tree_sha": expected_runtime_tree_sha.lower(),
            "artifact_digest": _artifact_digest(expected_runtime_tree_sha),
        },
        "ui": {"rendered": True, "body_nonempty": True, "error_surface_detected": False},
    }
    proof["evidence_digest"] = _digest(proof)
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-tree-sha", required=True)
    parser.add_argument("--expected-runtime-sha", required=True)
    parser.add_argument("--expected-runtime-tree-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = probe(
        url=args.url,
        expected_sha=args.expected_sha,
        expected_tree_sha=args.expected_tree_sha,
        expected_runtime_sha=args.expected_runtime_sha,
        expected_runtime_tree_sha=args.expected_runtime_tree_sha,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
