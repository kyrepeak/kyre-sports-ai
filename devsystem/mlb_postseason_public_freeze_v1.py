"""Read-only public certification for MLB postseason next-slate behavior.

This verifier changes no product state. It drives the deployed Streamlit UI,
selects MLB -> Slate, and proves the Sep. 28 off-day rolls forward to the
verified Sep. 29 postseason slate instead of presenting provider diagnostics.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _choose, _find_app_frame


EXPECTED_REQUESTED_DAY = "2026-09-28"
EXPECTED_NEXT_DAY = "2026-09-29"
EXPECTED_GAME_TEXT = "4 games loaded"
EXPECTED_MARKERS = (
    "MLB Postseason",
    "NEXT SLATE",
    EXPECTED_NEXT_DAY,
    EXPECTED_GAME_TEXT,
)
FORBIDDEN_RENDERED_MARKERS = (
    "No games reached the slate",
    "provider diagnostics",
)


def _body(frame) -> str:
    return frame.locator("body").inner_text(timeout=5000)


def _route_to_mlb_slate(page):
    frame, scans = _find_app_frame(page, timeout_seconds=75.0)
    _choose(page, frame, 0, "MLB")
    page.wait_for_timeout(3500)

    frame, more = _find_app_frame(page, timeout_seconds=75.0)
    scans.extend(more)
    combos = frame.get_by_role("combobox")
    if combos.count() < 2:
        raise BrowserQAFailure(
            f"MLB market selector missing; comboboxes={combos.count()} body={_body(frame)[:2500]!r}"
        )
    _choose(page, frame, 1, "Slate")
    page.wait_for_timeout(4500)

    frame, final = _find_app_frame(page, timeout_seconds=75.0)
    scans.extend(final)
    return frame, scans


def _certify_once(page, production_url: str, artifact_dir: Path) -> dict:
    page.goto(production_url, wait_until="domcontentloaded", timeout=90000)
    frame, scans = _route_to_mlb_slate(page)

    deadline = time.monotonic() + 60.0
    body = ""
    while time.monotonic() < deadline:
        body = _body(frame)
        if all(marker in body for marker in EXPECTED_MARKERS):
            break
        page.wait_for_timeout(2500)
        frame, more = _find_app_frame(page, timeout_seconds=20.0)
        scans.extend(more)
    else:
        raise BrowserQAFailure(
            "Public MLB postseason markers not ready. "
            f"Expected={EXPECTED_MARKERS!r} body={body[:5000]!r}"
        )

    forbidden = [marker for marker in FORBIDDEN_RENDERED_MARKERS if marker in body]
    if forbidden:
        raise BrowserQAFailure(
            f"Public MLB slate still renders failure diagnostics: {forbidden!r}. "
            f"body={body[:5000]!r}"
        )

    screenshot = artifact_dir / "mlb_postseason_public_step4_green.png"
    page.screenshot(path=str(screenshot), full_page=True)

    return {
        "status": "GREEN",
        "production_url": production_url,
        "requested_off_day": EXPECTED_REQUESTED_DAY,
        "next_slate_day": EXPECTED_NEXT_DAY,
        "expected_game_text": EXPECTED_GAME_TEXT,
        "markers": list(EXPECTED_MARKERS),
        "forbidden_markers_absent": True,
        "app_frame_url": frame.url,
        "frame_scan_count": len(scans),
        "body_excerpt": body[:5000],
        "screenshot": str(screenshot),
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }


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
                context = browser.new_context(viewport={"width": 1440, "height": 1200})
                page = context.new_page()
                try:
                    result = _certify_once(page, production_url, artifacts)
                    result["attempts"] = attempts + [{"status": "success"}]
                    evidence = artifacts / "mlb_postseason_public_step4_evidence.json"
                    evidence.write_text(
                        json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    print("MLB_POSTSEASON_STEP4_PUBLIC_GREEN")
                    print(json.dumps(result, indent=2, sort_keys=True))
                    return result
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    attempts.append({"status": "not_ready", "error": last_error[:1500]})
                finally:
                    context.close()

                if time.monotonic() >= deadline:
                    break
                time.sleep(max(1.0, poll_seconds))
        finally:
            browser.close()

    failure = {
        "status": "BLOCKED",
        "production_url": production_url,
        "attempts": attempts,
        "last_error": last_error,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (artifacts / "mlb_postseason_public_step4_evidence.json").write_text(
        json.dumps(failure, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(
        "MLB_POSTSEASON_STEP4_PUBLIC_BLOCKED: public rollout did not satisfy "
        f"the contract within {max_rollout_seconds:.0f}s. {last_error}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default="https://pickvault.streamlit.app")
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/mlb-postseason-public-step4",
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
