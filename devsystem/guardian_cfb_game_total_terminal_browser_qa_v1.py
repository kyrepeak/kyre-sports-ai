"""KYRE GUARDIAN browser proof for the current CFB Game Total terminal page.

This is intentionally version-neutral. It certifies the application-facing
terminal runtime, not any frozen V150/V152/V163/V164/V184/V185 presentation.
Historical certification files remain byte-stable and keep their own manifests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from playwright.sync_api import sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:8501"
ROUTE_SPORT_KEY = "sport"
ROUTE_MARKET_KEY = "market"
ROUTE_SPORT = "cfb"
ROUTE_MARKET = "game-total"
SELECTION_QUERY_KEY = "cfbgt_game"
REQUIRED_VISIBLE = (
    "KYRE SPORTS AI • CFB GAME TOTALS",
    "Game Total Intelligence",
    "UPCOMING MATCHUPS",
)
EMPTY_SLATE_MARKER = (
    "No upcoming CFB games remain on this slate. "
    "Started and completed games are hidden automatically."
)
ACTIVE_BOARD_VISIBLE = (
    "Selected matchup",
    "MARKET TOTAL",
    "KYRE PROJECTED TOTAL",
    "KYRE O/U PROBABILITY",
)
FORBIDDEN_ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError",
    "ImportError:",
    "SyntaxError:",
    "NameError:",
    "KeyError:",
    "This app has encountered an error",
)
VIEWPORTS = (
    ("tablet", 1067, 1536),
    ("mobile", 390, 844),
)


class GuardianTerminalBrowserQAFailure(RuntimeError):
    pass


def _artifact_dir(path: str | Path) -> Path:
    result = Path(path)
    result.mkdir(parents=True, exist_ok=True)
    return result


def _wait_for_health(base_url: str, timeout_seconds: float = 120.0) -> dict[str, int]:
    deadline = time.monotonic() + timeout_seconds
    root_status = 0
    health_status = 0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            health = requests.get(
                base_url.rstrip("/") + "/_stcore/health",
                timeout=5,
                headers={"User-Agent": "KyreGuardian-TerminalBrowserQA/1.0"},
            )
            root = requests.get(
                base_url.rstrip("/") + "/",
                timeout=10,
                headers={"User-Agent": "KyreGuardian-TerminalBrowserQA/1.0"},
            )
            health_status = health.status_code
            root_status = root.status_code
            if health_status == 200 and root_status == 200 and "streamlit" in root.text.casefold():
                return {"root_http": root_status, "health_http": health_status}
        except Exception as exc:  # pragma: no cover - real browser/CI path
            last_error = exc
        time.sleep(2)
    raise GuardianTerminalBrowserQAFailure(
        "Streamlit health did not become ready: "
        f"root={root_status} health={health_status} last_error={last_error!r}"
    )


def _route_url(base_url: str) -> str:
    query = urlencode(
        {
            ROUTE_SPORT_KEY: ROUTE_SPORT,
            ROUTE_MARKET_KEY: ROUTE_MARKET,
        }
    )
    return base_url.rstrip("/") + "/?" + query


def _query_state(page) -> dict[str, list[str]]:
    return parse_qs(urlparse(page.url).query)


def _assert_route(page) -> dict[str, list[str]]:
    query = _query_state(page)
    sport = (query.get(ROUTE_SPORT_KEY) or [""])[-1]
    market = (query.get(ROUTE_MARKET_KEY) or [""])[-1]
    if sport != ROUTE_SPORT or market != ROUTE_MARKET:
        raise GuardianTerminalBrowserQAFailure(
            f"Canonical terminal route drifted: sport={sport!r} market={market!r} url={page.url!r}"
        )
    return query


def _forbidden_error(body: str) -> str | None:
    for marker in FORBIDDEN_ERROR_MARKERS:
        if marker in body:
            return marker
    return None


def _current_surface(body: str) -> bool:
    return all(token in body for token in REQUIRED_VISIBLE)


def _find_current_frame(page, timeout_seconds: float = 90.0):
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            scans.append({"index": index, "url": frame.url, "body_start": body[:800]})
            if _current_surface(body):
                return frame, body, scans
        last_scan = scans
        page.wait_for_timeout(750)
    raise GuardianTerminalBrowserQAFailure(
        "Current CFB Game Total terminal surface was not found: "
        + json.dumps(last_scan, ensure_ascii=False)
    )


def _assert_current_contract(frame, body: str) -> dict[str, Any]:
    missing = [token for token in REQUIRED_VISIBLE if token not in body]
    if missing:
        raise GuardianTerminalBrowserQAFailure(
            "Current terminal visible contract missing: " + " | ".join(missing)
        )
    forbidden = _forbidden_error(body)
    if forbidden:
        raise GuardianTerminalBrowserQAFailure(
            f"Current terminal route contains runtime error marker: {forbidden}"
        )

    empty = EMPTY_SLATE_MARKER in body
    rail = frame.locator(".cfbgt4-rail")
    chips = frame.locator("a.cfbgt4-chip")
    cards = frame.locator(".cfbgt6-card")
    if empty:
        if chips.count() or cards.count():
            raise GuardianTerminalBrowserQAFailure(
                "Empty upcoming slate rendered actionable matchup controls"
            )
        return {
            "state": "EMPTY_CURRENT_SLATE",
            "chip_count": 0,
            "card_count": 0,
        }

    missing_board = [token for token in ACTIVE_BOARD_VISIBLE if token not in body]
    if missing_board:
        raise GuardianTerminalBrowserQAFailure(
            "Active current board contract missing: " + " | ".join(missing_board)
        )
    if rail.count() != 1:
        raise GuardianTerminalBrowserQAFailure(
            f"Expected one current matchup rail, found {rail.count()}"
        )
    chip_count = chips.count()
    if chip_count < 1:
        raise GuardianTerminalBrowserQAFailure("Current matchup rail has no actionable game")
    if cards.count() != 1:
        raise GuardianTerminalBrowserQAFailure(
            f"Expected one selected current decision card, found {cards.count()}"
        )
    selected = frame.locator("a.cfbgt4-chip.selected")
    if selected.count() != 1:
        raise GuardianTerminalBrowserQAFailure(
            f"Expected exactly one selected current matchup chip, found {selected.count()}"
        )
    return {
        "state": "ACTIVE_UPCOMING_SLATE",
        "chip_count": chip_count,
        "card_count": cards.count(),
    }


def _assert_in_viewport(locator, label: str) -> dict[str, float]:
    bounds = locator.evaluate(
        """el => {
            const r = el.getBoundingClientRect();
            return {
                left: Number(r.left),
                right: Number(r.right),
                width: Number(r.width),
                viewportWidth: Number(window.innerWidth)
            };
        }"""
    )
    if float(bounds["left"]) < -2.0:
        raise GuardianTerminalBrowserQAFailure(
            f"{label} extends left of viewport: {bounds!r}"
        )
    if float(bounds["right"]) > float(bounds["viewportWidth"]) + 2.0:
        raise GuardianTerminalBrowserQAFailure(
            f"{label} extends right of viewport: {bounds!r}"
        )
    return {key: float(value) for key, value in bounds.items()}


def _wait_for_selection_query(page, expected: str, timeout_seconds: float = 45.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        last = (_query_state(page).get(SELECTION_QUERY_KEY) or [""])[-1]
        if last == expected:
            return last
        page.wait_for_timeout(400)
    raise GuardianTerminalBrowserQAFailure(
        f"Current matchup selection did not persist in {SELECTION_QUERY_KEY}: "
        f"expected={expected!r} actual={last!r} url={page.url!r}"
    )


def _selection_target(frame) -> tuple[Any | None, str]:
    chips = frame.locator("a.cfbgt4-chip")
    for index in range(chips.count()):
        chip = chips.nth(index)
        classes = str(chip.get_attribute("class") or "")
        href = str(chip.get_attribute("href") or "")
        event_id = (parse_qs(urlparse(href).query).get(SELECTION_QUERY_KEY) or [""])[-1]
        if event_id and "selected" not in classes.split():
            return chip, event_id
    return None, ""


def run(
    *,
    base_url: str = DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/guardian-cfb-game-total-terminal-browser",
) -> dict[str, Any]:
    artifacts = _artifact_dir(artifact_dir)
    health = _wait_for_health(base_url)
    result: dict[str, Any] = {
        "status": "GREEN",
        "authority": "KYRE_GUARDIAN_ONLY",
        "health": health,
        "route": {ROUTE_SPORT_KEY: ROUTE_SPORT, ROUTE_MARKET_KEY: ROUTE_MARKET},
        "historical_surface_required": False,
        "fixed_historical_date_required": False,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(_route_url(base_url), wait_until="domcontentloaded", timeout=120000)
            _assert_route(page)
            frame, body, initial_scan = _find_current_frame(page)
            current = _assert_current_contract(frame, body)
            result["initial"] = {**current, "frame_scan": initial_scan}

            target, target_event = _selection_target(frame)
            if current["state"] == "ACTIVE_UPCOMING_SLATE" and target is not None:
                target.click(timeout=30000)
                _wait_for_selection_query(page, target_event)
                _assert_route(page)
                frame, body, click_scan = _find_current_frame(page)
                clicked = _assert_current_contract(frame, body)
                result["selection"] = {
                    "tested": True,
                    "event_id": target_event,
                    "state": clicked["state"],
                    "frame_scan": click_scan,
                }

                page.reload(wait_until="domcontentloaded", timeout=120000)
                _wait_for_selection_query(page, target_event)
                _assert_route(page)
                frame, body, reload_scan = _find_current_frame(page)
                reloaded = _assert_current_contract(frame, body)
                result["reload"] = {
                    "selection_persisted": True,
                    "event_id": target_event,
                    "state": reloaded["state"],
                    "frame_scan": reload_scan,
                }
            else:
                result["selection"] = {
                    "tested": False,
                    "reason": (
                        "empty current slate"
                        if current["state"] == "EMPTY_CURRENT_SLATE"
                        else "fewer than two actionable upcoming games"
                    ),
                }

            responsive: dict[str, Any] = {}
            for label, width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(250)
                frame, body, _ = _find_current_frame(page)
                snapshot = _assert_current_contract(frame, body)
                shell = frame.locator(".cfbgt5-shell").first
                if shell.count() != 1:
                    raise GuardianTerminalBrowserQAFailure(
                        f"{label} current terminal shell missing"
                    )
                geometry = {"shell": _assert_in_viewport(shell, f"{label} shell")}
                if snapshot["state"] == "ACTIVE_UPCOMING_SLATE":
                    card = frame.locator(".cfbgt6-card").first
                    geometry["selected_card"] = _assert_in_viewport(
                        card, f"{label} selected card"
                    )
                responsive[label] = {
                    "viewport": {"width": width, "height": height},
                    "state": snapshot["state"],
                    "geometry": geometry,
                }
                page.screenshot(
                    path=str(artifacts / f"guardian_cfb_game_total_{label}_green.png"),
                    full_page=True,
                )
            result["responsive"] = responsive

            evidence_path = artifacts / "guardian_cfb_game_total_terminal_browser.json"
            evidence_path.write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            result["evidence"] = str(evidence_path)
            print("GUARDIAN_CFB_GAME_TOTAL_TERMINAL_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/guardian-cfb-game-total-terminal-browser",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
