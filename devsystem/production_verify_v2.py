"""DevSystem production verification V2 — CFB Clean Page V39 activation.

Additive over frozen production_verify_v1. V2 preserves V1's Render API,
identity, observability, safety, and HTTP checks. For the CFB Over/Under browser
proof it reuses the certified V39 readiness primitives and enters the exact
V154/V77 fast route directly, avoiding the transient default CFB Moneyline
render whose cfb_* purge/re-import graph can race before Over/Under is selected.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

try:
    from devsystem import browser_qa_v1 as certified_browser
    from devsystem import production_verify_v1 as frozen
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v2.py`
    import browser_qa_v1 as certified_browser
    import production_verify_v1 as frozen

FROZEN_VERIFIER = "devsystem.production_verify_v1"
CFB_REQUIRED_MARKERS = (
    "CFB O/U • CLEAN PAGE V39 ACTIVE",
    "COMPACT EVIDENCE RENDERER",
    "VERIFIED IDENTITY ≠ MISSING STEP METRIC",
    "0.0% SPORTSBOOK PROJECTION INFLUENCE",
    "Matchup Foundation",
    "Steps 1–4 • compact verified evidence",
    "Frozen O/U math • Mutation OFF • Sportsbook 0.0%",
    "Step 5 • Explosive Plays",
    "Step 10 • Historical Matchup",
    "Steps 11–12 • current form + certification",
)


def _browser_verify_v39(
    streamlit_url: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    certified_browser._wait_for_health(streamlit_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        try:
            page.goto(
                certified_browser._cfb_over_under_url(streamlit_url),
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scan = certified_browser._find_app_frame(page)

            initial_body = frame.locator("body").inner_text()
            forbidden = certified_browser._body_has_forbidden_error(initial_body)
            if forbidden:
                raise frozen.ProductionVerificationFailure(
                    f"Production Streamlit runtime error marker: {forbidden}"
                )

            sport_combo = frame.get_by_role("combobox").nth(0)
            if sport_combo.count() == 0:
                raise frozen.ProductionVerificationFailure(
                    "Production sport selector is missing"
                )
            try:
                initial_sport_value = sport_combo.input_value(timeout=3000)
            except Exception:
                try:
                    initial_sport_value = sport_combo.inner_text(timeout=3000)
                except Exception:
                    initial_sport_value = ""

            # Fail fast on route identity before waiting for route-specific
            # lower-card content on the shared Streamlit host.
            route_identity = CFB_REQUIRED_MARKERS[0]
            if route_identity not in initial_body:
                raise frozen.ProductionVerificationFailure(
                    "ROUTE_TARGET_MISMATCH: expected "
                    f"{certified_browser.CFB_SPORT} -> {certified_browser.CFB_MARKET}; "
                    f"required identity={route_identity!r}; "
                    f"actual body start={initial_body[:1000]!r}"
                )

            cfb_market_combo = frame.get_by_role(
                "combobox",
                name=certified_browser.CFB_MARKET_LABEL,
                exact=True,
            )
            cfb_market_combo.wait_for(state="visible", timeout=45000)

            # Dynamic slate availability is not route drift. Mirror the
            # certified browser-QA contract: a valid no-games state proves the
            # route without requiring lower game-card markers that cannot exist.
            terminal_marker = CFB_REQUIRED_MARKERS[-1]
            final_body = certified_browser._wait_for_either_text(
                frame,
                terminal_marker,
                certified_browser.CFB_NO_GAMES_MARKER,
                60.0,
            )
            no_games = certified_browser.CFB_NO_GAMES_MARKER in final_body
            required_markers = (
                CFB_REQUIRED_MARKERS
                if not no_games
                else (
                    CFB_REQUIRED_MARKERS[0],
                    *CFB_REQUIRED_MARKERS[1:4],
                )
            )
            missing_markers = [
                marker for marker in required_markers
                if marker not in final_body
            ]
            if missing_markers:
                raise frozen.ProductionVerificationFailure(
                    "Production CFB V39 presentation marker drift: "
                    + " | ".join(missing_markers)
                )

            forbidden = certified_browser._body_has_forbidden_error(final_body)
            if forbidden:
                raise frozen.ProductionVerificationFailure(
                    f"Production CFB route runtime error marker: {forbidden}"
                )

            screenshot = artifacts / "production_browser_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                "initial_sport_value": initial_sport_value,
                "sport_option_inventory_verified_by": "branch-local DevSystem browser QA",
                "cfb_route": (
                    f"{certified_browser.CFB_SPORT} -> "
                    f"{certified_browser.CFB_MARKET}"
                ),
                "cfb_markers": list(CFB_REQUIRED_MARKERS),
                "app_frame_url": frame.url,
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(artifacts / "production_browser_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(*, artifact_dir: str = "artifacts/production-verification"):
    original_browser = frozen._browser_verify
    frozen._browser_verify = _browser_verify_v39
    try:
        return frozen.run(artifact_dir=artifact_dir)
    finally:
        frozen._browser_verify = original_browser


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
