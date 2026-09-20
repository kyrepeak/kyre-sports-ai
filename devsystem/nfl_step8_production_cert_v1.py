"""Step 8 one-time production certification.

Runs the full live 14-game audit from the frozen Step 8 proof, then verifies
that public Streamlit production has actually deployed the Step 7 fail-closed
NFL player-prop router by opening the Receptions route and requiring the exact
V187 fail-closed message.

This is certification-only. It does not mutate production or model behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import nfl_step8_full_14_game_cert_v1 as audit

STREAMLIT_URL = "https://kyre-sports-ai.streamlit.app"
EXPECTED_RECEPTIONS_TEXT = (
    "Receptions is fail-closed at the Step 7 app identity gate."
)
FORBIDDEN_MARKERS = (
    "Traceback",
    "SyntaxError",
    "ModuleNotFoundError",
    "KeyError",
    "TypeError:",
)


class Step8ProductionCertificationFailure(RuntimeError):
    pass


def _find_step7_frame(page, timeout_seconds: float = 150.0):
    deadline = time.monotonic() + timeout_seconds
    scans: list[dict[str, str]] = []
    while time.monotonic() < deadline:
        scans = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            scans.append(
                {
                    "index": str(index),
                    "url": str(frame.url or ""),
                    "body_start": body[:700],
                }
            )
            if EXPECTED_RECEPTIONS_TEXT in body:
                for marker in FORBIDDEN_MARKERS:
                    if marker in body:
                        raise Step8ProductionCertificationFailure(
                            f"production body contains forbidden runtime marker: {marker}"
                        )
                return frame, body, scans
        page.wait_for_timeout(1000)
    raise Step8ProductionCertificationFailure(
        "public Streamlit never exposed the Step 7 fail-closed Receptions router; "
        + json.dumps(scans, ensure_ascii=False)
    )


def verify_public_streamlit(artifact_dir: Path) -> dict[str, object]:
    query = urlencode(
        {
            "ks_jump_sport": "NFL",
            "ks_jump_market": "Receptions",
        }
    )
    target = STREAMLIT_URL.rstrip("/") + "/?" + query
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1100, "height": 1500})
        try:
            page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, scans = _find_step7_frame(page)
            screenshot = artifact_dir / "nfl_step8_production_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                "streamlit_url": STREAMLIT_URL,
                "route": "NFL -> Receptions",
                "step7_fail_closed_text_verified": True,
                "frame_url": str(frame.url or ""),
                "outer_url": str(page.url or ""),
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
        finally:
            browser.close()


def run(*, artifact_dir: str | Path) -> dict[str, object]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # Full 14-game live source/market proof.
    result_code = audit.main()
    if result_code != 0:
        raise Step8ProductionCertificationFailure(
            f"14-game audit returned non-zero: {result_code}"
        )

    public = verify_public_streamlit(artifacts)
    result = {
        "status": "GREEN",
        "locked_date": audit.DATE,
        "expected_games": 14,
        "expected_teams": 28,
        "public_streamlit": public,
        "steps_1_7_frozen": True,
        "certification_only": True,
    }
    result_path = artifacts / "nfl_step8_production_certification.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("NFL_STEP8_PRODUCTION_CERTIFICATION_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/nfl-step8-production-certification",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _args()
    run(artifact_dir=args.artifact_dir)
