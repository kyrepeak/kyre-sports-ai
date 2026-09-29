"""Read-only public certification for the WNBA PRA production surface.

This verifier changes no product state. It drives the deployed PickVault
Streamlit app through WNBA -> PRA and proves the Step-1 API-owned transport and
Step-2 clean presentation are visible in production across desktop, tablet, and
mobile viewports. Frozen model/market/Monte-Carlo behavior is not modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _choose, _find_app_frame


REQUIRED_MARKERS = (
    "WNBA PRA",
    "Kyre Sports API owned",
    "Advanced diagnostics",
)

VALID_STATE_MARKERS = (
    "No WNBA games on this date",
    "Slate & data status",
)

FORBIDDEN_RENDERED_MARKERS = (
    "V2.4 WNBA Slate Verification",
    "V2.7 Current Player Pool Check",
    "Step 6 — WNBA PRA Market Grading",
    "Step 7 — WNBA Matchup + Pace Adjustment",
    "WNBA SportsGameOdds Bridge",
    "SPORTSGAMEODDS_API_KEY is missing",
    "SPORTSGAMEODDS_API_KEY",
    "SportsGameOdds WNBA",
)

VIEWPORTS = (
    ("desktop", 1440, 1200),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
)


def _body(frame) -> str:
    return frame.locator("body").inner_text(timeout=5000)


def _route_to_wnba_pra(page):
    frame, scans = _find_app_frame(page, timeout_seconds=75.0)
    _choose(page, frame, 0, "WNBA")
    page.wait_for_timeout(3500)

    frame, more = _find_app_frame(page, timeout_seconds=75.0)
    scans.extend(more)
    combos = frame.get_by_role("combobox")
    if combos.count() < 2:
        raise BrowserQAFailure(
            f"WNBA market selector missing; comboboxes={combos.count()} body={_body(frame)[:2500]!r}"
        )
    _choose(page, frame, 1, "PRA")
    page.wait_for_timeout(5500)

    frame, final = _find_app_frame(page, timeout_seconds=75.0)
    scans.extend(final)
    return frame, scans


def _certify_viewport(browser, production_url: str, artifact_dir: Path, name: str, width: int, height: int) -> dict:
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    try:
        page.goto(production_url, wait_until="domcontentloaded", timeout=90000)
        frame, scans = _route_to_wnba_pra(page)

        deadline = time.monotonic() + 60.0
        body = ""
        state_marker = ""
        while time.monotonic() < deadline:
            body = _body(frame)
            required_ok = all(marker in body for marker in REQUIRED_MARKERS)
            state_marker = next((marker for marker in VALID_STATE_MARKERS if marker in body), "")
            if required_ok and state_marker:
                break
            page.wait_for_timeout(2500)
            frame, more = _find_app_frame(page, timeout_seconds=20.0)
            scans.extend(more)
        else:
            raise BrowserQAFailure(
                "Public WNBA PRA markers not ready. "
                f"Required={REQUIRED_MARKERS!r} states={VALID_STATE_MARKERS!r} body={body[:6000]!r}"
            )

        forbidden = [marker for marker in FORBIDDEN_RENDERED_MARKERS if marker in body]
        if forbidden:
            raise BrowserQAFailure(
                f"Public WNBA PRA still exposes legacy/provider diagnostics: {forbidden!r}. "
                f"body={body[:6000]!r}"
            )

        screenshot = artifact_dir / f"wnba_pra_step3_{name}_green.png"
        page.screenshot(path=str(screenshot), full_page=True)

        return {
            "status": "GREEN",
            "viewport": {"name": name, "width": width, "height": height},
            "state_marker": state_marker,
            "required_markers": list(REQUIRED_MARKERS),
            "forbidden_markers_absent": True,
            "app_frame_url": frame.url,
            "frame_scan_count": len(scans),
            "body_excerpt": body[:6000],
            "screenshot": str(screenshot),
        }
    finally:
        context.close()


def _certify_once(browser, production_url: str, artifact_dir: Path) -> dict:
    viewports = []
    for name, width, height in VIEWPORTS:
        viewports.append(
            _certify_viewport(
                browser,
                production_url,
                artifact_dir,
                name,
                width,
                height,
            )
        )

    states = sorted({item["state_marker"] for item in viewports})
    result = {
        "status": "GREEN",
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "api_ownership_marker": "Kyre Sports API owned",
        "clean_presentation_marker": "Advanced diagnostics",
        "valid_state_markers_observed": states,
        "legacy_provider_markers_absent": True,
        "responsive_viewports": [item["viewport"] for item in viewports],
        "viewports": viewports,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return result


def run_public_cert(
    *,
    production_url: str,
    artifact_dir: str | Path,
    max_rollout_seconds: float = 420.0,
    poll_seconds: float = 20.0,
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + max_rollout_seconds
    attempts = []
    last_error = ""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            while True:
                try:
                    result = _certify_once(browser, production_url, artifacts)
                    result["attempts"] = attempts + [{"status": "success"}]
                    evidence = artifacts / "wnba_pra_step3_public_evidence.json"
                    evidence.write_text(
                        json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    print("WNBA_PRA_STEP3_PUBLIC_GREEN")
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return result
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    attempts.append({"status": "not_ready", "error": last_error[:2000]})

                if time.monotonic() >= deadline:
                    break
                time.sleep(max(1.0, poll_seconds))
        finally:
            browser.close()

    failure = {
        "status": "BLOCKED",
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "attempts": attempts,
        "last_error": last_error,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (artifacts / "wnba_pra_step3_public_evidence.json").write_text(
        json.dumps(failure, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(
        "WNBA_PRA_STEP3_PUBLIC_BLOCKED: production did not satisfy the "
        f"final-freeze contract within {max_rollout_seconds:.0f}s. {last_error}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default="https://pickvault.streamlit.app")
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-step3-public-freeze",
    )
    parser.add_argument("--max-rollout-seconds", type=float, default=420.0)
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    args = parser.parse_args()

    run_public_cert(
        production_url=args.production_url,
        artifact_dir=args.artifact_dir,
        max_rollout_seconds=args.max_rollout_seconds,
        poll_seconds=args.poll_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
