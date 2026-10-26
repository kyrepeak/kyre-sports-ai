"""Live MONSTER Step 2G production convergence probe.

Uses one Chromium document load as both stable-alias health evidence and the
runtime-identity/UI proof. This avoids a separate urllib health request whose
redirect semantics do not match Streamlit's browser flow.
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


def browser_health_evidence(*, document_status: int, document_url: str) -> dict[str, Any]:
    status = int(document_status)
    url = str(document_url or "").strip()
    if not url or status < 200 or status >= 400:
        raise RuntimeError(f"MONSTER stable alias browser health failed: status={status} url={url!r}")
    return {"source": "browser_document", "status": status, "url": url, "healthy": True}


def probe(*, url: str, expected_sha: str, expected_tree_sha: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    stable_alias = url.rstrip("/")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(stable_alias, wait_until="domcontentloaded", timeout=120_000)
        if response is None:
            browser.close()
            raise RuntimeError("MONSTER stable alias returned no browser document response")
        health = browser_health_evidence(document_status=response.status, document_url=page.url)
        marker = page.locator("#monster-runtime-identity")
        marker.wait_for(state="attached", timeout=120_000)
        encoded = marker.get_attribute("data-monster-runtime-identity")
        if not encoded:
            browser.close()
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
        "stable_alias": stable_alias,
        "health": health,
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
