"""Live MONSTER Step 2G production convergence probe.

Runs only as supporting evidence after a monster-main push. It loads the stable
production alias once in Chromium, waits for the MONSTER runtime identity marker,
and fails closed unless live runtime identity equals the exact pushed SHA/tree.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "MONSTER_STEP2G_LIVE_CONVERGENCE_PROOF_V1"
RUNTIME_SCHEMA = "MONSTER_STEP2G_RUNTIME_IDENTITY_V1"
ROUTER_OWNER = "MONSTER_CANONICAL_ROUTER"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def expected_identity(sha: str, tree_sha: str) -> dict[str, str]:
    return {
        "owner": "MONSTER",
        "sha": sha.lower(),
        "tree_sha": tree_sha.lower(),
        "artifact_digest": hashlib.sha256(tree_sha.lower().encode("ascii")).hexdigest(),
        "deployment_id": f"monster-streamlit-{sha[:12].lower()}",
        "entrypoint": "app.py",
        "router_owner": ROUTER_OWNER,
        "schema_version": RUNTIME_SCHEMA,
    }


def probe(*, url: str, expected_sha: str, expected_tree_sha: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    health_url = url.rstrip("/") + "/_stcore/health"
    with urllib.request.urlopen(health_url, timeout=30) as response:
        health_status = response.status
        health_body = response.read().decode("utf-8", errors="replace").strip()
    if health_status != 200 or "ok" not in health_body.lower():
        raise RuntimeError(f"MONSTER stable alias health failed: {health_status} {health_body!r}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        if response is None or response.status >= 400:
            raise RuntimeError("MONSTER production page did not load successfully")
        marker = page.locator("#monster-runtime-identity")
        marker.wait_for(state="attached", timeout=120_000)
        encoded = marker.get_attribute("data-monster-runtime-identity")
        if not encoded:
            raise RuntimeError("MONSTER runtime identity marker is missing payload")
        live_identity = json.loads(html.unescape(encoded))
        body_text = page.locator("body").inner_text(timeout=30_000)
        browser.close()

    expected = expected_identity(expected_sha, expected_tree_sha)
    if live_identity != expected:
        raise RuntimeError(f"PRODUCTION_NOT_UPDATED: live identity {live_identity!r} != expected {expected!r}")
    lowered = body_text.lower()
    if not body_text.strip() or "encountered an error" in lowered or "traceback" in lowered:
        raise RuntimeError("USER_FACING_PARITY_FAILURE: production body is blank or errored")

    proof = {
        "schema_version": SCHEMA_VERSION,
        "authority": "MONSTER_ONLY",
        "stable_alias": url.rstrip("/"),
        "health": {"status": health_status, "body": health_body},
        "runtime_identity": live_identity,
        "ui": {"rendered": True, "body_nonempty": True, "error_surface_detected": False},
    }
    proof["evidence_digest"] = _digest(proof)
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-tree-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = probe(url=args.url, expected_sha=args.expected_sha, expected_tree_sha=args.expected_tree_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
