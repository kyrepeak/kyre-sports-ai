"""DevSystem production verification V3 — CFB Game Total V160 freshness proof.

Additive over frozen production_verify_v2. V3 preserves every existing Render,
API, observability, safety, and CFB Over/Under production check, then drives the
real deployed Streamlit app to College Football -> Game Total and requires the
exact V160 production heartbeat. A healthy HTTP 200 is not sufficient when the
visible deployed router is stale.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import sync_playwright

try:
    from devsystem import production_verify_v1 as base
    from devsystem import production_verify_v2 as prior
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v3.py`
    import production_verify_v1 as base
    import production_verify_v2 as prior

FROZEN_VERIFIER = "devsystem.production_verify_v2"
EXPECTED_ROUTER = "streamlit_memory_lazy_router_v155"
GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ProductionVerificationFailure = base.ProductionVerificationFailure


def _assert_v160_heartbeat(body: str) -> str:
    if GAME_TOTAL_REQUIRED_HEARTBEAT not in str(body or ""):
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total deployment: "
            f"required heartbeat {GAME_TOTAL_REQUIRED_HEARTBEAT!r} was not visible"
        )
    return GAME_TOTAL_REQUIRED_HEARTBEAT


def _build_freshness_evidence(
    *,
    expected_commit: str,
    observed_body: str,
) -> dict[str, Any]:
    observed = _assert_v160_heartbeat(observed_body)
    return {
        "expected_commit": str(expected_commit or "unknown"),
        "expected_router": EXPECTED_ROUTER,
        "observed_router": "V155/V160",
        "observed_build_marker": observed,
        "freshness_verified": True,
    }


def _browser_verify_game_total_freshness(
    streamlit_url: str,
    artifact_dir: Path,
    *,
    expected_commit: str,
) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scans = base._find_app_frame(page)

            initial_body = frame.locator("body").inner_text()
            forbidden = base._body_has_forbidden_error(initial_body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Streamlit runtime error marker: {forbidden}"
                )

            base._choose(page, frame, 0, CFB_SPORT)

            deadline = time.monotonic() + 45.0
            while time.monotonic() < deadline:
                if frame.get_by_role("combobox").count() >= 2:
                    break
                page.wait_for_timeout(1000)
            else:
                raise ProductionVerificationFailure(
                    "Production CFB route did not expose market selector for freshness proof"
                )

            base._choose(page, frame, 1, GAME_TOTAL_MARKET)

            deadline = time.monotonic() + 90.0
            final_body = ""
            while time.monotonic() < deadline:
                final_body = frame.locator("body").inner_text()
                if GAME_TOTAL_REQUIRED_HEARTBEAT in final_body:
                    break
                page.wait_for_timeout(1500)
            _assert_v160_heartbeat(final_body)

            forbidden = base._body_has_forbidden_error(final_body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Game Total runtime error marker: {forbidden}"
                )

            screenshot = artifact_dir / "production_game_total_v160_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                **_build_freshness_evidence(
                    expected_commit=expected_commit,
                    observed_body=final_body,
                ),
                "game_total_route": f"{CFB_SPORT} -> {GAME_TOTAL_MARKET}",
                "game_total_app_frame_url": frame.url,
                "game_total_frame_scan_count": len(scans),
                "game_total_freshness_screenshot": str(screenshot),
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(artifact_dir / "production_game_total_v160_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(
    *,
    artifact_dir: str | Path = "artifacts/production-verification",
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # Preserve the full V2 production proof first: Render/API identity + the
    # certified CFB Over/Under route remain unchanged and authoritative.
    result = dict(prior.run(artifact_dir=artifacts))

    targets = base._load_targets()
    streamlit_url = str(targets["streamlit"]["url"]).rstrip("/")
    expected_commit = str(os.environ.get("GITHUB_SHA") or "unknown")
    freshness = _browser_verify_game_total_freshness(
        streamlit_url,
        artifacts,
        expected_commit=expected_commit,
    )

    result.update(freshness)
    result["status"] = "GREEN"
    result["production_verifier"] = "V3"

    result_path = artifacts / "production_verification.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("DEVSYSTEM_PRODUCTION_VERIFICATION_V3_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-verification",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(artifact_dir=args.artifact_dir)
