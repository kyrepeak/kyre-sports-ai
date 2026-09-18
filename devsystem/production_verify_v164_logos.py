"""Production verification for CFB Game Total V164 exact team logos.

V164 is presentation-only. The existing V5 production workflow remains the
separate required V163 persistence gate. This verifier proves only the additive
V164 exact ESPN team-logo rendering in the live Streamlit deployment, avoiding
duplicate concurrent browser certification against the same app process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import production_verify_v5 as v163
from devsystem import production_verify_v1 as base

CERT_DATE = "2026-09-19"
CERT_EVENT_ID = "401869940"
AWAY_TEAM = "Coastal Carolina"
HOME_TEAM = "Delaware"
AWAY_TEAM_ID = "324"
HOME_TEAM_ID = "48"
REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"
REQUIRED_PATCH_MARKER = "CFB_GAME_TOTAL_V164_BLANK_EVENT_ID_HANDOFF_PATCH_ACTIVE"


class ProductionVerificationV164Failure(RuntimeError):
    pass


def _image_state(locator) -> dict:
    return locator.evaluate(
        """img => ({
            src: img.currentSrc || img.src || "",
            complete: Boolean(img.complete),
            naturalWidth: Number(img.naturalWidth || 0),
            naturalHeight: Number(img.naturalHeight || 0)
        })"""
    )


def _wait_image_state(locator, timeout_ms: int = 15000) -> dict:
    """Wait for the external logo request to settle, then return strict image state."""
    locator.wait_for(state="attached", timeout=timeout_ms)
    return locator.evaluate(
        """(img, timeout) => new Promise((resolve) => {
            const snapshot = () => ({
                src: img.currentSrc || img.src || "",
                complete: Boolean(img.complete),
                naturalWidth: Number(img.naturalWidth || 0),
                naturalHeight: Number(img.naturalHeight || 0)
            });
            if (img.complete) {
                resolve(snapshot());
                return;
            }
            let done = false;
            const finish = () => {
                if (done) return;
                done = true;
                resolve(snapshot());
            };
            img.addEventListener("load", finish, {once: true});
            img.addEventListener("error", finish, {once: true});
            setTimeout(finish, timeout);
        })""",
        timeout_ms,
    )


def _assert_exact_pair(frame, selector: str, label: str) -> list[dict]:
    images = frame.locator(selector)
    if images.count() != 2:
        raise ProductionVerificationV164Failure(
            f"{label} expected two exact logo images; found {images.count()}"
        )
    states = [_wait_image_state(images.nth(i)) for i in range(images.count())]
    urls = [str(row["src"]) for row in states]
    for team_id in (AWAY_TEAM_ID, HOME_TEAM_ID):
        suffix = f"/{team_id}.png"
        if not any(url.endswith(suffix) for url in urls):
            raise ProductionVerificationV164Failure(
                f"{label} missing ESPN team logo {suffix}: {urls}"
            )
    for row in states:
        if not row["complete"] or row["naturalWidth"] <= 0 or row["naturalHeight"] <= 0:
            raise ProductionVerificationV164Failure(
                f"{label} image failed to load: {row}"
            )
    return states



def _wait_for_v164_patch_deployment(
    page,
    *,
    timeout_seconds: float = 240.0,
):
    """Reload until the live app proves this exact logo patch is deployed."""
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    last_scans: list[dict] = []
    last_error = ""
    while time.monotonic() < deadline:
        try:
            frame, body, scans = v163._wait_for_top_level_selection(
                page,
                CERT_EVENT_ID,
                timeout_seconds=45.0,
            )
            last_body = body
            last_scans = scans
            last_error = ""
            if (
                REQUIRED_HEARTBEAT in body
                and REQUIRED_PATCH_MARKER in body
            ):
                return frame, body, scans
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise ProductionVerificationV164Failure(
        "V164 logo proof timed out waiting for the current Streamlit patch: "
        f"required_marker={REQUIRED_PATCH_MARKER!r} "
        f"last_error={last_error!r} scans={last_scans!r} "
        f"body_start={last_body[:500]!r}"
    )


def verify_live_v164(
    streamlit_url: str,
    *,
    artifact_dir: str | Path = "artifacts/production-v164-logos",
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    query = urlencode(
        {
            v163.ROUTE_QUERY_SPORT: v163.CFB_SPORT,
            v163.ROUTE_QUERY_MARKET: v163.GAME_TOTAL_MARKET,
            v163.DATE_QUERY_KEY: CERT_DATE,
            v163.EVENT_QUERY_KEY: CERT_EVENT_ID,
        }
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/?" + query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, scans = _wait_for_v164_patch_deployment(page)
            if REQUIRED_HEARTBEAT not in body:
                raise ProductionVerificationV164Failure(
                    f"missing V164 production heartbeat: {REQUIRED_HEARTBEAT}"
                )
            if REQUIRED_PATCH_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing current V164 logo patch marker: {REQUIRED_PATCH_MARKER}"
                )
            if AWAY_TEAM not in body or HOME_TEAM not in body:
                raise ProductionVerificationV164Failure(
                    f"certified matchup not visible: {AWAY_TEAM} @ {HOME_TEAM}"
                )
            event_id = v163._event_from_url(page.url)
            if event_id != CERT_EVENT_ID:
                raise ProductionVerificationV164Failure(
                    f"certified event did not persist: expected={CERT_EVENT_ID!r} "
                    f"actual={event_id!r}"
                )

            header = _assert_exact_pair(frame, "img.gt159-logo", "matchup header")
            evidence = _assert_exact_pair(
                frame,
                "img.gt160-evidence-logo",
                "team evidence",
            )

            screenshot = artifacts / "production_cfb_game_total_v164_logos_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "date": CERT_DATE,
                "event_id": event_id,
                "away_team": AWAY_TEAM,
                "away_team_id": AWAY_TEAM_ID,
                "home_team": HOME_TEAM,
                "home_team_id": HOME_TEAM_ID,
                "header_logos": header,
                "evidence_logos": evidence,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
            (artifacts / "production_v164_logo_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return result
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    targets = base._load_targets()
    parser.add_argument(
        "--streamlit-url",
        default=str(targets["streamlit"]["url"]).rstrip("/"),
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-v164-logos",
    )
    args = parser.parse_args()

    logos = verify_live_v164(
        args.streamlit_url,
        artifact_dir=args.artifact_dir,
    )
    result = {
        "status": "GREEN",
        "required_separate_gate": "DevSystem production verification V5",
        "v164_exact_team_logos": logos,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    print("CFB_GAME_TOTAL_V164_PRODUCTION_LOGOS_GREEN")


if __name__ == "__main__":
    main()
