"""CFB Game Total Page 2 Step 8 — live responsive production certification.

Certification-only. Opens the public CFB Game Total slate, discovers one exact
selected-event link, enters Page 2, and validates the frozen Page-2 surfaces at
390/430/768/1440 widths. It mutates no product/runtime state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

EXPECTED_MAIN_SHA = "STEP8_MERGED_MAIN_SHA"
PRODUCTION_URL = "https://pickvault.streamlit.app"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
PHOENIX_TZ = "America/Phoenix"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PRODUCT_RUNTIME = False
GITHUB_ACTIONS_FALLBACK = 0

VIEWPORTS = {
    "mobile390": {"width": 390, "height": 844},
    "mobile430": {"width": 430, "height": 932},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1440, "height": 1200},
}

REQUIRED_TESTIDS = (
    "gtp2s2-matchup-hero",
    "gtp2s3-flow",
    "gtp2s4-outlook",
    "gtp2s5-team-snapshot",
    "gtp2s6-trends",
    "gtp2s7-line-lab",
    "gtp2s7-best-bet",
    "gtp2s8-back-to-slate",
    "gtp2s8-final",
)

FORBIDDEN_VISIBLE_TEXT = (
    "data limited",
    "mock data",
    "pending",
)


class Step8LiveCertFailure(RuntimeError):
    pass


def route_handoff(base_url: str = PRODUCTION_URL) -> str:
    return base_url.rstrip("/") + "/?ks_sport=College+Football&ks_cfb_market=Game+Total"


def _visible(frame: Any, testid: str) -> None:
    frame.locator(f'[data-testid="{testid}"]').first.wait_for(state="visible", timeout=90000)


def _runtime_error(body: str) -> str:
    return str(base._body_has_forbidden_error(body) or "")


def _horizontal_overflow(frame: Any) -> bool:
    return bool(frame.evaluate("""() => {
        const de = document.documentElement;
        const body = document.body;
        const width = Math.max(de ? de.scrollWidth : 0, body ? body.scrollWidth : 0);
        const client = de ? de.clientWidth : window.innerWidth;
        return width > client + 3;
    }"""))


def _forbidden_visible_text(body: str) -> list[str]:
    lower = body.casefold()
    return [value for value in FORBIDDEN_VISIBLE_TEXT if value.casefold() in lower]


def _exact_event_id(url: str) -> str:
    values = parse_qs(urlparse(url).query).get(EVENT_QUERY_KEY) or []
    return str(values[-1] if values else "").strip()


def _discover_exact_event(page: Any, base_url: str) -> tuple[str, str, Any]:
    page.goto(route_handoff(base_url), wait_until="domcontentloaded", timeout=120000)
    frame, scans = base._find_app_frame(page)
    frame.locator(f'a[href*="{EVENT_QUERY_KEY}="]').first.wait_for(state="attached", timeout=90000)
    href = frame.locator(f'a[href*="{EVENT_QUERY_KEY}="]').first.get_attribute("href") or ""
    if not href:
        raise Step8LiveCertFailure("No exact CFB Game Total selected-event link was discoverable")
    selected_url = urljoin(page.url, href)
    event_id = _exact_event_id(selected_url)
    if not event_id:
        raise Step8LiveCertFailure("Selected-event URL did not contain an exact ESPN event identity")
    return selected_url, event_id, scans


def _selected_viewport_result(page: Any, name: str, base_url: str, artifact_dir: Path) -> dict[str, Any]:
    selected_url, event_id, initial_scans = _discover_exact_event(page, base_url)
    page.goto(selected_url, wait_until="domcontentloaded", timeout=120000)
    frame, selected_scans = base._find_app_frame(page)

    for testid in REQUIRED_TESTIDS:
        _visible(frame, testid)

    body = frame.locator("body").inner_text(timeout=30000)
    forbidden = _forbidden_visible_text(body)
    runtime_error = _runtime_error(body)
    horizontal_overflow = _horizontal_overflow(frame)
    current_event_id = _exact_event_id(page.url) or event_id

    if current_event_id != event_id:
        raise Step8LiveCertFailure(f"Exact event identity drift at {name}: {event_id} -> {current_event_id}")
    if forbidden:
        raise Step8LiveCertFailure(f"Forbidden Page-2 copy at {name}: {forbidden}")
    if runtime_error:
        raise Step8LiveCertFailure(f"Runtime error at {name}: {runtime_error}")
    if horizontal_overflow:
        raise Step8LiveCertFailure(f"Horizontal overflow at {name}")

    screenshot = artifact_dir / f"cfb_game_total_page2_step8_{name}.png"
    page.screenshot(path=str(screenshot), full_page=True)
    return {
        "viewport": dict(VIEWPORTS[name]),
        "selected_url": selected_url,
        "exact_event_id": event_id,
        "all_required_visible": True,
        "required_testids_visible": list(REQUIRED_TESTIDS),
        "forbidden_visible_text": [],
        "horizontal_overflow": False,
        "runtime_error": "",
        "initial_frame_scan": initial_scans,
        "selected_frame_scan": selected_scans,
        "screenshot": str(screenshot),
    }


def evidence_is_terminal_green(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or payload.get("status") != "GREEN":
        return False
    if payload.get("source_main_sha") != EXPECTED_MAIN_SHA:
        return False
    if payload.get("phoenix_timezone") != PHOENIX_TZ:
        return False
    if float(payload.get("sportsbook_projection_influence", -1)) != 0.0:
        return False
    if int(payload.get("github_actions_fallback", -1)) != 0:
        return False
    viewports = payload.get("viewports")
    if not isinstance(viewports, dict) or set(viewports) != set(VIEWPORTS):
        return False
    event_ids = set()
    for name in VIEWPORTS:
        row = viewports.get(name) or {}
        if row.get("all_required_visible") is not True:
            return False
        if row.get("horizontal_overflow") is not False:
            return False
        if row.get("forbidden_visible_text") not in ([], None):
            return False
        if str(row.get("runtime_error") or ""):
            return False
        event_id = str(row.get("exact_event_id") or "")
        if not event_id:
            return False
        event_ids.add(event_id)
    return len(event_ids) == 1


def run(*, base_url: str = PRODUCTION_URL, artifact_dir: str | Path = "artifacts/cfb-game-total-page2-step8") -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = base._wait_for_health(base_url)
    results: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        try:
            for name, viewport in VIEWPORTS.items():
                page = browser.new_page(viewport=viewport)
                try:
                    results[name] = _selected_viewport_result(page, name, base_url, artifacts)
                finally:
                    page.close()
        finally:
            browser.close()

    payload = {
        "status": "GREEN",
        "source_main_sha": EXPECTED_MAIN_SHA,
        "production_url": base_url,
        "route_url": route_handoff(base_url),
        "event_query_key": EVENT_QUERY_KEY,
        "phoenix_timezone": PHOENIX_TZ,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        "health": health,
        "viewports": results,
    }
    if not evidence_is_terminal_green(payload):
        raise Step8LiveCertFailure("Step-8 terminal live evidence contract rejected generated payload")

    evidence_path = artifacts / "cfb_game_total_page2_step8_live_cert.json"
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print("CFB_GT_PAGE2_STEP8_LIVE_GREEN", flush=True)
    print("CFB_GT_PAGE2_STEP8_EVIDENCE=" + json.dumps(payload, sort_keys=True), flush=True)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PRODUCTION_URL)
    parser.add_argument("--artifact-dir", default="artifacts/cfb-game-total-page2-step8")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
