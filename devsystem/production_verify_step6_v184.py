"""Dedicated production certification for CFB Game Total Step 6.

Certifies the V184 Scoring Creation surface independently from frozen Steps
1-5. The verifier follows the current live Game Total selector rather than a
hard-coded historical event, waits for the V184 DOM, and requires the complete
READY / 100% / 12-of-12 contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

from devsystem import production_verify_v5 as v163_nav


class Step6ProductionVerificationFailure(RuntimeError):
    pass


GREEN_MARKER = "CFB_GAME_TOTAL_V184_STEP6_PRODUCTION_GREEN"
STEP6_MARKER = "CFB_GAME_TOTAL_STEP6_SCORING_CREATION_ACTIVE"
STEP6_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"
STEP6_ROOT_SELECTOR = (
    'details.gt184-step6[data-testid="gt157-step-6"]'
    f'[data-step6-marker="{STEP6_MARKER}"]'
    f'[data-step6-deployment-marker="{STEP6_DEPLOYMENT_MARKER}"]'
)
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
CERT_QUERY_KEY = "ks_cfb_step6_cert"
CERT_SURFACE_MARKER = "CFB_GAME_TOTAL_V184_STEP6_CERT_SNAPSHOT_V1_ACTIVE"
CERT_CANDIDATES = (
    {
        "event_id": "401869940",
        "game_date": "2026-09-19",
        "matchup": "Coastal Carolina @ Delaware",
        "wait_seconds": 210.0,
    },
    {
        "event_id": "401856685",
        "game_date": "2026-09-19",
        "matchup": "Florida State @ Alabama",
        "wait_seconds": 90.0,
    },
)


def _query_value(url: str, key: str) -> str:
    values = parse_qs(urlparse(url).query).get(key) or []
    return str(values[-1] if values else "").strip()


def _event_from_url(url: str) -> str:
    return _query_value(url, EVENT_QUERY_KEY)


def _load_streamlit_url() -> str:
    targets_path = Path(__file__).resolve().parents[1] / "devsystem" / "production_targets_v1.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    return str(targets["streamlit"]["url"]).rstrip("/")


def _wait_for_live_step6(page, timeout_seconds: float = 300.0):
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    last_error = ""
    last_scans: list[dict] = []

    while time.monotonic() < deadline:
        try:
            frame, body, scans = v163_nav._find_v163_frame(
                page,
                timeout_seconds=min(45.0, max(5.0, deadline - time.monotonic())),
            )
            last_body = str(body or "")
            last_scans = scans
            root = frame.locator(STEP6_ROOT_SELECTOR).last
            root_count = root.count()
            if root_count > 0:
                root.wait_for(state="attached", timeout=5000)
                return frame, root, body, scans
            last_error = "V184 Step 6 root not live yet"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"[:1200]

        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise Step6ProductionVerificationFailure(
        "V184 Step 6 production surface did not become live: "
        f"last_error={last_error!r} scans={last_scans!r} "
        f"body_start={last_body[:3000]!r}"
    )


def _assert_step6(root) -> dict:
    marker = str(root.get_attribute("data-step6-marker") or "").strip()
    deployment_marker = str(
        root.get_attribute("data-step6-deployment-marker") or ""
    ).strip()
    state = str(root.get_attribute("data-step6-state") or "").strip()
    coverage = str(root.get_attribute("data-step6-coverage") or "").strip()
    ready_attr = str(root.get_attribute("data-step6-ready-tiles") or "").strip()

    tiles = root.locator('[data-testid="gt184-step6-stat-tile"]')
    tile_count = tiles.count()
    ready_tiles = root.locator(
        '[data-testid="gt184-step6-stat-tile"][data-ready="true"]'
    ).count()
    body_text = root.inner_text(timeout=10000)

    if marker != STEP6_MARKER:
        raise Step6ProductionVerificationFailure(
            f"Step 6 marker mismatch: expected={STEP6_MARKER!r} actual={marker!r}"
        )
    if deployment_marker != STEP6_DEPLOYMENT_MARKER:
        raise Step6ProductionVerificationFailure(
            "Step 6 deployment marker mismatch: "
            f"expected={STEP6_DEPLOYMENT_MARKER!r} actual={deployment_marker!r}"
        )
    if state != "READY":
        raise Step6ProductionVerificationFailure(
            f"Step 6 state is not READY: {state!r}"
        )
    if coverage != "100":
        raise Step6ProductionVerificationFailure(
            f"Step 6 coverage is not 100: {coverage!r}"
        )
    if ready_attr != "12" or tile_count != 12 or ready_tiles != 12:
        raise Step6ProductionVerificationFailure(
            "Step 6 tile completeness failed: "
            f"attr={ready_attr!r} tiles={tile_count} ready_tiles={ready_tiles}"
        )
    if "DATA LIMITED" in body_text:
        raise Step6ProductionVerificationFailure(
            "Step 6 READY surface still contains DATA LIMITED"
        )
    if "SPORTSBOOK INFLUENCE 0.0%" not in body_text:
        raise Step6ProductionVerificationFailure(
            "Step 6 sportsbook-influence protection marker is missing"
        )
    if "PROJECTION MUTATION OFF" not in body_text:
        raise Step6ProductionVerificationFailure(
            "Step 6 projection-mutation protection marker is missing"
        )

    return {
        "status": state,
        "coverage": int(coverage),
        "tile_count": tile_count,
        "ready_tiles": ready_tiles,
        "marker": marker,
        "deployment_marker": deployment_marker,
        "sportsbook_influence": 0.0,
        "projection_mutation": False,
    }


def verify_live_step6(
    streamlit_url: str,
    *,
    artifact_dir: str | Path = "artifacts/production-step6-v184",
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1800})
        try:
            for index, candidate in enumerate(CERT_CANDIDATES, start=1):
                cert_date = str(candidate["game_date"])
                cert_event_id = str(candidate["event_id"])
                cert_matchup = str(candidate["matchup"])
                query = urlencode(
                    {
                        ROUTE_QUERY_SPORT: CFB_SPORT,
                        ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
                        DATE_QUERY_KEY: cert_date,
                        EVENT_QUERY_KEY: cert_event_id,
                        CERT_QUERY_KEY: "1",
                    }
                )
                try:
                    page.goto(
                        streamlit_url.rstrip("/") + "/?" + query,
                        wait_until="domcontentloaded",
                        timeout=120000,
                    )
                    frame, root, body, scans = _wait_for_live_step6(
                        page,
                        timeout_seconds=float(candidate["wait_seconds"]),
                    )

                    cert_surface = frame.locator(
                        '[data-testid="gt184-step6-cert-surface"]'
                        f'[data-step6-cert-marker="{CERT_SURFACE_MARKER}"]'
                    ).last
                    cert_surface_present = cert_surface.count() > 0

                    event_id = _event_from_url(page.url) or _event_from_url(frame.url)
                    if event_id != cert_event_id:
                        raise Step6ProductionVerificationFailure(
                            "V184 certification event did not persist: "
                            f"expected={cert_event_id!r} actual={event_id!r} "
                            f"page_url={page.url!r} frame_url={frame.url!r}"
                        )

                    selected_date = (
                        _query_value(page.url, DATE_QUERY_KEY)
                        or _query_value(frame.url, DATE_QUERY_KEY)
                    )
                    if selected_date != cert_date:
                        raise Step6ProductionVerificationFailure(
                            "V184 certification date did not persist: "
                            f"expected={cert_date!r} actual={selected_date!r} "
                            f"page_url={page.url!r} frame_url={frame.url!r}"
                        )

                    step6 = _assert_step6(root)
                    screenshot = artifacts / "production_step6_v184_green.png"
                    page.screenshot(path=str(screenshot), full_page=True)

                    result = {
                        "status": "GREEN",
                        "candidate_index": index,
                        "date": selected_date,
                        "event_id": str(event_id),
                        "matchup": cert_matchup,
                        "cert_surface_marker": (
                            CERT_SURFACE_MARKER if cert_surface_present else ""
                        ),
                        "cert_surface_present": cert_surface_present,
                        "step6": step6,
                        "frame_scan_count": len(scans),
                        "screenshot": str(screenshot),
                    }
                    (artifacts / "production_step6_v184_evidence.json").write_text(
                        json.dumps(result, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                    return result
                except Exception as exc:
                    failures.append(
                        f"{cert_event_id} {cert_matchup}: "
                        f"{type(exc).__name__}: {exc}"[:2200]
                    )
                    continue
        finally:
            browser.close()

    raise Step6ProductionVerificationFailure(
        "All V184 Step 6 certification candidates failed: "
        + " | ".join(failures)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--streamlit-url",
        default=_load_streamlit_url(),
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-step6-v184",
    )
    args = parser.parse_args()
    result = verify_live_step6(
        args.streamlit_url,
        artifact_dir=args.artifact_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(GREEN_MARKER)


if __name__ == "__main__":
    main()
