"""CFB Game Total native rebuild Step 8 — mobile + production certification.

Certification-only. This final-step owner does not mutate Page 1, Page 2, model,
projection, probability, providers, or sportsbook influence. It verifies the
current immutable Render API identity and exercises the public CFB Game Total
Page-1 -> exact-event Page-2 flow at mobile/tablet/desktop widths.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

MODEL_VERSION = "CFB GAME TOTAL • MOBILE + PRODUCTION • STEP 8 V1"
SOURCE_MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
PRODUCTION_URL = "https://pickvault.streamlit.app"
RENDER_URL = "https://kyre-sports-api.onrender.com"
RENDER_SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
RENDER_SOURCE_BRANCH = "mlb-step17b-shared-host-cert"
RENDER_CERTIFIED_COMMIT = "879c28265efde1810a5e30352fa2dcb269c1052a"
RENDER_OBSERVABILITY_VERSION = "KYRE_OBSERVABILITY_V1"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
PHOENIX_TZ = "America/Phoenix"
PAGE1_TESTID = "gt163-game-strip"
PHOENIX_DAY_TESTID = "gt241-phoenix-day-selector"
PAGE1_FRAME_MARKERS = ("PHOENIX TIME", "GAMES ON THIS DAY")
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
GITHUB_ACTIONS_FALLBACK = 0

VIEWPORTS = {
    "mobile390": {"width": 390, "height": 844},
    "mobile430": {"width": 430, "height": 932},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1440, "height": 1200},
}

PAGE2_REQUIRED_TESTIDS = (
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

PAGE1_FORBIDDEN_VISIBLE_TEXT = (
    "data limited",
    "espn id unavailable",
)
PAGE2_FORBIDDEN_VISIBLE_TEXT = (
    "data limited",
    "mock data",
    "pending",
)


class Step8MobileProductionFailure(RuntimeError):
    pass


def authoritative_phoenix_day() -> str:
    """Return the one authoritative current calendar day for the native slate."""
    return datetime.now(ZoneInfo(PHOENIX_TZ)).date().isoformat()


def page1_route(base_url: str = PRODUCTION_URL) -> str:
    query = urlencode(
        {
            "ks_sport": "College Football",
            "ks_cfb_market": "Game Total",
            "ks_cfb_game_total_date": authoritative_phoenix_day(),
        }
    )
    return base_url.rstrip("/") + "/?" + query


def _event_from_url(url: str) -> str:
    values = parse_qs(urlparse(str(url or "")).query).get(EVENT_QUERY_KEY) or []
    return str(values[-1] if values else "").strip()


def _visible(frame: Any, testid: str, timeout_ms: int = 90000) -> None:
    frame.locator(f'[data-testid="{testid}"]').first.wait_for(
        state="visible",
        timeout=timeout_ms,
    )


def _find_cfb_frame(
    page: Any,
    *,
    required_markers: tuple[str, ...] = (),
    required_testids: tuple[str, ...] = (),
    timeout_seconds: float = 120.0,
) -> tuple[Any, list[dict[str, Any]]]:
    """Find the native CFB frame without relying on legacy selector controls."""
    if not required_markers and not required_testids:
        raise Step8MobileProductionFailure("CFB_FRAME_MATCH_CRITERIA_REQUIRED")

    deadline = time.monotonic() + timeout_seconds
    last_scans: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            lower = body.casefold()

            if "get this app back up" in lower:
                try:
                    wake = frame.get_by_text("Yes, get this app back up!", exact=False)
                    if wake.count() > 0:
                        wake.first.click()
                        page.wait_for_timeout(3000)
                        continue
                except Exception:
                    pass

            marker_hits = [m for m in required_markers if m.casefold() in lower]
            testid_hits: list[str] = []
            for testid in required_testids:
                try:
                    if frame.locator(f'[data-testid="{testid}"]').count() > 0:
                        testid_hits.append(testid)
                except Exception:
                    pass

            scans.append(
                {
                    "index": index,
                    "url": str(getattr(frame, "url", "") or ""),
                    "marker_hits": marker_hits,
                    "testid_hits": testid_hits,
                    "body_start": body[:600],
                }
            )
            if (
                len(marker_hits) == len(required_markers)
                and len(testid_hits) == len(required_testids)
            ):
                return frame, scans

        last_scans = scans
        page.wait_for_timeout(750)

    raise Step8MobileProductionFailure(
        "CFB_NATIVE_FRAME_NOT_FOUND:"
        + json.dumps(last_scans, ensure_ascii=False)
    )


def _horizontal_overflow(frame: Any) -> bool:
    return bool(
        frame.evaluate(
            """() => {
                const de = document.documentElement;
                const body = document.body;
                const width = Math.max(de ? de.scrollWidth : 0, body ? body.scrollWidth : 0);
                const client = de ? de.clientWidth : window.innerWidth;
                return width > client + 3;
            }"""
        )
    )


def _forbidden(body: str, values: tuple[str, ...]) -> list[str]:
    lower = str(body or "").casefold()
    return [value for value in values if value.casefold() in lower]


def _runtime_error(body: str) -> str:
    return str(base._body_has_forbidden_error(str(body or "")) or "")


def verify_render_identity() -> dict[str, Any]:
    response = requests.get(
        RENDER_URL.rstrip("/") + "/health/details",
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "KyreSportsAI-CFB-Step8/1.0",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    runtime = payload.get("runtime") or {}
    observed = {
        "service_id": str(runtime.get("service_id") or ""),
        "source_branch": str(runtime.get("deploy_branch") or ""),
        "certified_commit": str(runtime.get("deploy_commit") or ""),
        "branch_aligned": runtime.get("branch_aligned"),
        "observability_version": payload.get("observability_version"),
    }
    expected = {
        "service_id": RENDER_SERVICE_ID,
        "source_branch": RENDER_SOURCE_BRANCH,
        "certified_commit": RENDER_CERTIFIED_COMMIT,
        "branch_aligned": True,
        "observability_version": RENDER_OBSERVABILITY_VERSION,
    }
    if observed != expected:
        raise Step8MobileProductionFailure(
            "RENDER_PRODUCTION_IDENTITY_DRIFT:"
            + json.dumps({"expected": expected, "observed": observed}, sort_keys=True)
        )
    return {"status": "GREEN", **observed}


def _page1_result(
    page: Any,
    name: str,
    artifact_dir: Path,
) -> tuple[dict[str, Any], str, str]:
    page.goto(page1_route(), wait_until="domcontentloaded", timeout=120000)
    frame, scans = _find_cfb_frame(
        page,
        required_markers=PAGE1_FRAME_MARKERS,
        required_testids=(PHOENIX_DAY_TESTID, PAGE1_TESTID),
        timeout_seconds=120.0,
    )
    _visible(frame, PHOENIX_DAY_TESTID)
    _visible(frame, PAGE1_TESTID)

    body = frame.locator("body").inner_text(timeout=30000)
    forbidden = _forbidden(body, PAGE1_FORBIDDEN_VISIBLE_TEXT)
    runtime_error = _runtime_error(body)
    overflow = _horizontal_overflow(frame)
    phoenix_today = "TODAY" in body and "PHOENIX TIME" in body

    links = frame.locator(
        f'[data-testid="{PAGE1_TESTID}"] '
        f'a.gt163-game-link[href*="{EVENT_QUERY_KEY}="]'
    )
    if links.count() < 1:
        raise Step8MobileProductionFailure(f"PAGE1_NO_EXACT_EVENT_LINK:{name}")
    href = str(links.first.get_attribute("href") or "")
    selected_url = urljoin(page.url, href)
    event_id = _event_from_url(selected_url)
    if not event_id:
        raise Step8MobileProductionFailure(f"PAGE1_EVENT_ID_MISSING:{name}")
    if forbidden:
        raise Step8MobileProductionFailure(f"PAGE1_FORBIDDEN_COPY:{name}:{forbidden}")
    if runtime_error:
        raise Step8MobileProductionFailure(f"PAGE1_RUNTIME_ERROR:{name}:{runtime_error}")
    if overflow:
        raise Step8MobileProductionFailure(f"PAGE1_HORIZONTAL_OVERFLOW:{name}")
    if not phoenix_today:
        raise Step8MobileProductionFailure(f"PAGE1_PHOENIX_TODAY_MISSING:{name}")

    screenshot = artifact_dir / f"cfb_game_total_step8_{name}_page1.png"
    page.screenshot(path=str(screenshot), full_page=True)
    return (
        {
            "game_strip_visible": True,
            "phoenix_day_selector_visible": True,
            "phoenix_today_visible": True,
            "exact_event_id": event_id,
            "exact_event_href": href,
            "horizontal_overflow": False,
            "forbidden_visible_text": [],
            "runtime_error": "",
            "frame_scan": scans,
            "screenshot": str(screenshot),
        },
        selected_url,
        event_id,
    )


def _page2_result(
    page: Any,
    name: str,
    selected_url: str,
    event_id: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    page.goto(selected_url, wait_until="domcontentloaded", timeout=120000)
    frame, scans = _find_cfb_frame(
        page,
        required_testids=PAGE2_REQUIRED_TESTIDS,
        timeout_seconds=120.0,
    )
    for testid in PAGE2_REQUIRED_TESTIDS:
        _visible(frame, testid)

    body = frame.locator("body").inner_text(timeout=30000)
    forbidden = _forbidden(body, PAGE2_FORBIDDEN_VISIBLE_TEXT)
    runtime_error = _runtime_error(body)
    overflow = _horizontal_overflow(frame)
    wrapper_event = _event_from_url(page.url)
    frame_event = _event_from_url(str(getattr(frame, "url", "") or ""))
    observed_events = {value for value in (wrapper_event, frame_event) if value}
    if observed_events and observed_events != {event_id}:
        raise Step8MobileProductionFailure(
            f"PAGE2_EVENT_ID_DRIFT:{name}:expected={event_id}:"
            f"observed={sorted(observed_events)}"
        )
    if forbidden:
        raise Step8MobileProductionFailure(f"PAGE2_FORBIDDEN_COPY:{name}:{forbidden}")
    if runtime_error:
        raise Step8MobileProductionFailure(f"PAGE2_RUNTIME_ERROR:{name}:{runtime_error}")
    if overflow:
        raise Step8MobileProductionFailure(f"PAGE2_HORIZONTAL_OVERFLOW:{name}")

    screenshot = artifact_dir / f"cfb_game_total_step8_{name}_page2.png"
    page.screenshot(path=str(screenshot), full_page=True)
    return {
        "all_required_visible": True,
        "required_testids_visible": list(PAGE2_REQUIRED_TESTIDS),
        "exact_event_id": event_id,
        "wrapper_event_id": wrapper_event,
        "frame_event_id": frame_event,
        "horizontal_overflow": False,
        "forbidden_visible_text": [],
        "runtime_error": "",
        "frame_scan": scans,
        "screenshot": str(screenshot),
    }


def evidence_is_terminal_green(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or payload.get("status") != "GREEN":
        return False
    if payload.get("source_main_sha") != SOURCE_MAIN_SHA:
        return False
    if payload.get("phoenix_timezone") != PHOENIX_TZ:
        return False
    if float(payload.get("sportsbook_projection_influence", -1)) != 0.0:
        return False
    if int(payload.get("github_actions_fallback", -1)) != 0:
        return False
    identity = payload.get("render_identity") or {}
    if identity.get("certified_commit") != RENDER_CERTIFIED_COMMIT:
        return False
    viewports = payload.get("viewports")
    if not isinstance(viewports, dict) or set(viewports) != set(VIEWPORTS):
        return False
    for name in VIEWPORTS:
        row = viewports.get(name) or {}
        page1 = row.get("page1") or {}
        page2 = row.get("page2") or {}
        if (
            page1.get("game_strip_visible") is not True
            or page1.get("phoenix_today_visible") is not True
        ):
            return False
        if (
            page1.get("horizontal_overflow") is not False
            or page2.get("horizontal_overflow") is not False
        ):
            return False
        if (
            page1.get("forbidden_visible_text") not in ([], None)
            or page2.get("forbidden_visible_text") not in ([], None)
        ):
            return False
        if str(page1.get("runtime_error") or "") or str(page2.get("runtime_error") or ""):
            return False
        event1 = str(page1.get("exact_event_id") or "")
        event2 = str(page2.get("exact_event_id") or "")
        if not event1 or event1 != event2:
            return False
        if page2.get("all_required_visible") is not True:
            return False
    return True


def run_public(
    *,
    base_url: str = PRODUCTION_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-step8",
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = base._wait_for_health(base_url)
    render_identity = verify_render_identity()
    rows: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        try:
            for name, viewport in VIEWPORTS.items():
                page = browser.new_page(viewport=viewport)
                try:
                    page1, selected_url, event_id = _page1_result(
                        page,
                        name,
                        artifacts,
                    )
                    page2 = _page2_result(
                        page,
                        name,
                        selected_url,
                        event_id,
                        artifacts,
                    )
                    rows[name] = {
                        "viewport": dict(viewport),
                        "page1": page1,
                        "page2": page2,
                    }
                finally:
                    page.close()
        finally:
            browser.close()

    payload = {
        "status": "GREEN",
        "model_version": MODEL_VERSION,
        "source_main_sha": SOURCE_MAIN_SHA,
        "production_url": base_url,
        "page1_route": page1_route(base_url),
        "phoenix_timezone": PHOENIX_TZ,
        "phoenix_date": datetime.now(ZoneInfo(PHOENIX_TZ)).date().isoformat(),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        "render_identity": render_identity,
        "streamlit_health": health,
        "viewports": rows,
    }
    if not evidence_is_terminal_green(payload):
        raise Step8MobileProductionFailure("STEP8_TERMINAL_EVIDENCE_REJECTED")
    evidence = artifacts / "cfb_game_total_mobile_production_step8_v1.json"
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("CFB_GAME_TOTAL_STEP8_PUBLIC_GREEN", flush=True)
    print(
        "CFB_GAME_TOTAL_STEP8_PUBLIC_EVIDENCE="
        + json.dumps(payload, sort_keys=True),
        flush=True,
    )
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PRODUCTION_URL)
    parser.add_argument("--artifact-dir", default="artifacts/cfb-game-total-step8")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_public(base_url=args.base_url, artifact_dir=args.artifact_dir)
