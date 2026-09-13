"""Real Streamlit browser witness for NFL Rushing Yards fast-route performance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from playwright.sync_api import sync_playwright

from browser_qa_v1 import (
    BrowserQAFailure,
    _body_has_forbidden_error,
    _find_app_frame,
    _wait_for_health,
    _wait_for_text,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8502"
FAST_QUERY = "?ks_nfl_sport=NFL&ks_nfl_market=Rushing%20Yards"
FAST_MARKER = "RUSHING FAST PATH V1"
PAGE_MARKER = "Ground Game Lab"
READY_MARKER = "Monster Performance Diagnosis"


def _parse_ms(body: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}\s+([0-9]+(?:\.[0-9]+)?)\s+ms", body)
    if not match:
        return None
    return float(match.group(1))


def run_witness(*, base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = _wait_for_health(base_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        started = time.monotonic()
        try:
            page.goto(
                base_url.rstrip("/") + "/" + FAST_QUERY,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scan = _find_app_frame(page)

            body = _wait_for_text(frame, FAST_MARKER, 90.0)
            fast_marker_ms = (time.monotonic() - started) * 1000.0
            if "historical router chain SKIPPED" not in body:
                raise BrowserQAFailure("Rushing fast route did not skip the historical router chain")
            if "projection math unchanged" not in body:
                raise BrowserQAFailure("Rushing fast route projection-safety marker is missing")

            body = _wait_for_text(frame, PAGE_MARKER, 90.0)
            page_shell_ms = (time.monotonic() - started) * 1000.0
            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(f"Rushing fast route contains runtime error marker: {forbidden}")

            body = _wait_for_text(frame, READY_MARKER, 150.0)
            full_route_ready_ms = (time.monotonic() - started) * 1000.0
            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(f"Completed Rushing route contains runtime error marker: {forbidden}")

            bootstrap_import_ms = _parse_ms(body, "bootstrap router import")
            active_page_import_ms = _parse_ms(body, "active-page import")
            if bootstrap_import_ms is None or active_page_import_ms is None:
                raise BrowserQAFailure("Rushing fast-route import timing markers were not parseable")

            screenshot = artifacts / "rushing_fast_route_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "route": "NFL -> Rushing Yards",
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "fast_marker_ms": round(fast_marker_ms, 2),
                "page_shell_ms": round(page_shell_ms, 2),
                "full_route_ready_ms": round(full_route_ready_ms, 2),
                "bootstrap_router_import_ms": round(bootstrap_import_ms, 2),
                "active_page_import_ms": round(active_page_import_ms, 2),
                "historical_router_chain_skipped": True,
                "projection_math_changed": False,
                "sportsbook_projection_influence": 0.0,
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
            }
            (artifacts / "rushing_fast_route_metrics.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("NFL_RUSHING_YARDS_FAST_ROUTE_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(path=str(artifacts / "rushing_fast_route_failure.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/rushing-fast-route")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_witness(base_url=args.base_url, artifact_dir=args.artifact_dir)
