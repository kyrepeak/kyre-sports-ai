"""Live production certification for CFB Game Total V185 Step 6 visual parity.

This verifier is presentation-only. It waits for the V185 visual-parity marker on
live Streamlit production, then reuses the permanently frozen V184 Step 6
READY/100%/12-of-12 assertion so visual freshness and data integrity are proven
on the same live DOM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import production_verify_step6_v184 as frozen


class Step6V185ProductionVerificationFailure(RuntimeError):
    pass


GREEN_MARKER = "CFB_GAME_TOTAL_V185_STEP6_PRODUCTION_GREEN"
STEP6_VISUAL_MARKER = "CFB_GAME_TOTAL_STEP6_V185_VISUAL_PARITY_ACTIVE"
STEP6_PARITY_MARKER = "CFB_GAME_TOTAL_STEP6_TARGET_MOCK_PARITY_ACTIVE"
STEP6_ROOT_SELECTOR = (
    'details.gt184-step6.gt185-step6[data-testid="gt157-step-6"]'
    f'[data-step6-visual-marker="{STEP6_VISUAL_MARKER}"]'
    f'[data-step6-visual-parity-marker="{STEP6_PARITY_MARKER}"]'
)


def _wait_for_live_v185(page, timeout_seconds: float = 360.0):
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    last_error = ""
    last_scans: list[dict] = []

    while time.monotonic() < deadline:
        try:
            frame, body, scans = frozen.v163_nav._find_v163_frame(
                page,
                timeout_seconds=min(45.0, max(5.0, deadline - time.monotonic())),
            )
            last_body = str(body or "")
            last_scans = scans
            root = frame.locator(STEP6_ROOT_SELECTOR).last
            if root.count() > 0:
                root.wait_for(state="attached", timeout=5000)
                return frame, root, body, scans
            last_error = "V185 Step 6 visual-parity root not live yet"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"[:1200]

        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise Step6V185ProductionVerificationFailure(
        "V185 Step 6 production surface did not become live: "
        f"last_error={last_error!r} scans={last_scans!r} "
        f"body_start={last_body[:3000]!r}"
    )


def _assert_v185_visual(root) -> dict:
    frozen_contract = frozen._assert_step6(root)

    visual_marker = str(root.get_attribute("data-step6-visual-marker") or "").strip()
    parity_marker = str(
        root.get_attribute("data-step6-visual-parity-marker") or ""
    ).strip()
    if visual_marker != STEP6_VISUAL_MARKER:
        raise Step6V185ProductionVerificationFailure(
            f"V185 visual marker mismatch: expected={STEP6_VISUAL_MARKER!r} "
            f"actual={visual_marker!r}"
        )
    if parity_marker != STEP6_PARITY_MARKER:
        raise Step6V185ProductionVerificationFailure(
            f"V185 parity marker mismatch: expected={STEP6_PARITY_MARKER!r} "
            f"actual={parity_marker!r}"
        )

    battle_pairs = root.locator(".gt185-s6-battlepair").count()
    offense_panels = root.locator(".gt185-s6-panel.offense").count()
    defense_panels = root.locator(".gt185-s6-panel.defense").count()
    defense_tiles = root.locator('[data-testid="gt185-step6-defense-tile"]').count()
    matchup_heroes = root.locator(".gt185-s6-matchup").count()
    env_strips = root.locator(".gt185-s6-env").count()
    insight_grids = root.locator(".gt185-s6-insights").count()

    expected = {
        "battle_pairs": (battle_pairs, 2),
        "offense_panels": (offense_panels, 2),
        "defense_panels": (defense_panels, 2),
        "defense_tiles": (defense_tiles, 12),
        "matchup_heroes": (matchup_heroes, 1),
        "environment_strips": (env_strips, 1),
        "insight_grids": (insight_grids, 1),
    }
    mismatches = [
        f"{name}={actual} expected={wanted}"
        for name, (actual, wanted) in expected.items()
        if actual != wanted
    ]
    if mismatches:
        raise Step6V185ProductionVerificationFailure(
            "V185 target geometry mismatch: " + " | ".join(mismatches)
        )

    body_text = root.inner_text(timeout=10000)
    required_text = (
        "💥 Scoring Creation",
        "SCORING CREATION",
        "SCORING PREVENTION",
        "SCORING ENVIRONMENT",
        "MATCHUP READ",
        "BIGGEST ACCELERATOR",
        "BIGGEST SUPPRESSOR",
        "O/U IMPACT",
        "DATA CONFIDENCE",
    )
    missing = [token for token in required_text if token not in body_text]
    if missing:
        raise Step6V185ProductionVerificationFailure(
            "V185 required visible text missing: " + " | ".join(missing)
        )

    style = root.evaluate(
        """(el) => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const p = el.parentElement ? el.parentElement.getBoundingClientRect() : null;
            return {
                gridColumnStart: s.gridColumnStart,
                gridColumnEnd: s.gridColumnEnd,
                width: r.width,
                parentWidth: p ? p.width : 0,
            };
        }"""
    )
    if str(style.get("gridColumnStart") or "") != "1":
        raise Step6V185ProductionVerificationFailure(
            f"V185 Step 6 does not start at grid column 1: {style!r}"
        )
    if str(style.get("gridColumnEnd") or "") != "-1":
        raise Step6V185ProductionVerificationFailure(
            f"V185 Step 6 does not span through grid column -1: {style!r}"
        )
    width = float(style.get("width") or 0.0)
    parent_width = float(style.get("parentWidth") or 0.0)
    if parent_width > 0 and width / parent_width < 0.94:
        raise Step6V185ProductionVerificationFailure(
            f"V185 Step 6 is not full-width: {style!r}"
        )

    return {
        **frozen_contract,
        "visual_marker": visual_marker,
        "parity_marker": parity_marker,
        "battle_pairs": battle_pairs,
        "offense_panels": offense_panels,
        "defense_panels": defense_panels,
        "defense_tiles": defense_tiles,
        "matchup_heroes": matchup_heroes,
        "environment_strips": env_strips,
        "insight_grids": insight_grids,
        "grid_column_start": style.get("gridColumnStart"),
        "grid_column_end": style.get("gridColumnEnd"),
        "width": width,
        "parent_width": parent_width,
    }


def verify_live_v185(
    streamlit_url: str,
    *,
    artifact_dir: str | Path = "artifacts/production-step6-v185",
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
            for index, candidate in enumerate(frozen.CERT_CANDIDATES, start=1):
                cert_date = str(candidate["game_date"])
                cert_event_id = str(candidate["event_id"])
                cert_matchup = str(candidate["matchup"])
                query = urlencode(
                    {
                        frozen.ROUTE_QUERY_SPORT: frozen.CFB_SPORT,
                        frozen.ROUTE_QUERY_MARKET: frozen.GAME_TOTAL_MARKET,
                        frozen.DATE_QUERY_KEY: cert_date,
                        frozen.EVENT_QUERY_KEY: cert_event_id,
                        frozen.CERT_QUERY_KEY: "1",
                    }
                )
                try:
                    page.goto(
                        streamlit_url.rstrip("/") + "/?" + query,
                        wait_until="domcontentloaded",
                        timeout=120000,
                    )
                    frame, root, body, scans = _wait_for_live_v185(
                        page,
                        timeout_seconds=max(
                            360.0,
                            float(candidate.get("wait_seconds") or 0.0),
                        ),
                    )

                    event_id = (
                        frozen._event_from_url(page.url)
                        or frozen._event_from_url(frame.url)
                    )
                    if event_id != cert_event_id:
                        raise Step6V185ProductionVerificationFailure(
                            "V185 certification event did not persist: "
                            f"expected={cert_event_id!r} actual={event_id!r}"
                        )

                    selected_date = (
                        frozen._query_value(page.url, frozen.DATE_QUERY_KEY)
                        or frozen._query_value(frame.url, frozen.DATE_QUERY_KEY)
                    )
                    if selected_date != cert_date:
                        raise Step6V185ProductionVerificationFailure(
                            "V185 certification date did not persist: "
                            f"expected={cert_date!r} actual={selected_date!r}"
                        )

                    step6 = _assert_v185_visual(root)
                    screenshot = artifacts / "production_step6_v185_green.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    rootshot = artifacts / "production_step6_v185_root_green.png"
                    root.screenshot(path=str(rootshot))

                    result = {
                        "status": "GREEN",
                        "candidate_index": index,
                        "date": selected_date,
                        "event_id": str(event_id),
                        "matchup": cert_matchup,
                        "step6": step6,
                        "frame_scan_count": len(scans),
                        "screenshot": str(screenshot),
                        "root_screenshot": str(rootshot),
                    }
                    (artifacts / "production_step6_v185_evidence.json").write_text(
                        json.dumps(result, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                    return result
                except Exception as exc:
                    failures.append(
                        f"{cert_event_id} {cert_matchup}: "
                        f"{type(exc).__name__}: {exc}"[:2500]
                    )
                    continue
        finally:
            browser.close()

    raise Step6V185ProductionVerificationFailure(
        "All V185 Step 6 certification candidates failed: "
        + " | ".join(failures)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--streamlit-url", default=frozen._load_streamlit_url())
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-step6-v185",
    )
    args = parser.parse_args()
    result = verify_live_v185(
        args.streamlit_url,
        artifact_dir=args.artifact_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(GREEN_MARKER)


if __name__ == "__main__":
    main()
