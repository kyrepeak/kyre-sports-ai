"""Proof-only exact live Streamlit deployment identity check."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import _find_app_frame

EXPECTED_PRODUCT_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
DEPLOYMENT_SELECTOR = '[data-api2-exact-deployment="streamlit-runtime-v1"]'
RUNTIME_ATTESTATION_PATHS = (
    "app.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py",
    "wnba_pra_repair_v1_step2_team_identity.py",
    "wnba_pra_game_center_v2_step3.py",
)
ROOT = Path(__file__).resolve().parents[1]


def _git_blob(rel: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{rel}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=2.0,
    )
    return str(completed.stdout or "").strip().lower()


def _expected_bundle() -> str:
    blobs = {rel: _git_blob(rel) for rel in RUNTIME_ATTESTATION_PATHS}
    if any(len(value) != 40 for value in blobs.values()):
        raise RuntimeError("EXACT_DEPLOYMENT_EXPECTED_BUNDLE_UNRESOLVED")
    canonical = "\n".join(f"{path}={blobs[path]}" for path in sorted(blobs))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run(production_url: str) -> int:
    query = urlencode({"ks_jump_sport": "WNBA", "ks_jump_market": "PRA"})
    route_url = production_url.rstrip("/") + "/?" + query
    expected_bundle = _expected_bundle()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        try:
            page.goto(route_url, wait_until="domcontentloaded", timeout=120000)
            deadline = time.monotonic() + 90.0
            marker = None
            attempts = 0
            while time.monotonic() < deadline:
                attempts += 1
                try:
                    frame, _ = _find_app_frame(page, timeout_seconds=12.0)
                except Exception as exc:
                    print(f"LIVE_SHA_FRAME_WAIT attempt={attempts} error={type(exc).__name__}", flush=True)
                    page.wait_for_timeout(1000)
                    continue
                candidate = frame.locator(DEPLOYMENT_SELECTOR).first
                if candidate.count() > 0:
                    marker = candidate
                    break
                print(f"LIVE_SHA_MARKER_WAIT attempt={attempts}", flush=True)
                page.wait_for_timeout(1000)
            if marker is None:
                print("LIVE_SHA_MARKER_MISSING", flush=True)
                return 2

            observed = str(marker.get_attribute("data-production-sha") or "").strip().lower()
            health = str(marker.get_attribute("data-health-sha") or "").strip().lower()
            readiness = str(marker.get_attribute("data-readiness-sha") or "").strip().lower()
            ui = str(marker.get_attribute("data-ui-proof-sha") or "").strip().lower()
            runtime_bundle = str(marker.get_attribute("data-runtime-bundle-digest") or "").strip().lower()
            bundle_complete = str(marker.get_attribute("data-runtime-bundle-complete") or "").strip().lower() == "true"
            bundle_match = bundle_complete and runtime_bundle == expected_bundle
            exact = observed == EXPECTED_PRODUCT_SHA
            corroborated = health == observed and readiness == observed and ui == observed

            print(f"LIVE_SHA_EXPECTED={EXPECTED_PRODUCT_SHA}", flush=True)
            print(f"LIVE_SHA_OBSERVED={observed}", flush=True)
            print(f"LIVE_SHA_EXACT_MATCH={str(exact).lower()}", flush=True)
            print(f"LIVE_SHA_HEALTH_READY_UI_MATCH={str(corroborated).lower()}", flush=True)
            print(f"LIVE_RUNTIME_BUNDLE_MATCH={str(bundle_match).lower()}", flush=True)
            print("LIVE_DEPLOYMENT_STATE=" + ("DEPLOYMENT_PARITY" if exact and corroborated and bundle_match else "STALE_OR_INCOMPLETE"), flush=True)
            return 0 if exact and corroborated and bundle_match else 3
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default="https://pickvault.streamlit.app")
    parser.add_argument("--artifact-dir", default="artifacts/unused")
    args = parser.parse_args()
    return run(args.production_url)


if __name__ == "__main__":
    raise SystemExit(main())
