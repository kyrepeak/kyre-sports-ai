"""API 2 universal shell/route/Top public production certificate.

Proof-only. Does not mutate product state. Reproduces the user-visible defect:
MLB Slate cold start -> tap NFL -> NFL must become the sole rendered owner.
Also proves the permanent KYRE SPORTS AI shell and universal Top control.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://pick6vault.streamlit.app"


def _body(frame) -> str:
    try:
        return " ".join(frame.locator("body").inner_text(timeout=5000).split())
    except Exception:
        return ""


def _best_app_frame(page):
    candidates = []
    for frame in page.frames:
        text = _body(frame)
        if text:
            candidates.append((frame, text))
    if not candidates:
        return None, ""
    candidates.sort(
        key=lambda item: (
            "KYRE SPORTS" in item[1].upper(),
            any(token in item[1] for token in ("MLB Slate", "MLB slate date", "NFL Command Center", "NFL slate date")),
            len(item[1]),
        ),
        reverse=True,
    )
    return candidates[0]


def _wake_if_needed(page) -> None:
    for frame in page.frames:
        for label in ("Yes, get this app back up!", "Wake up", "Rerun"):
            try:
                button = frame.get_by_role("button", name=label, exact=True)
                if button.count() and button.first.is_visible():
                    button.first.click()
                    page.wait_for_timeout(800)
                    return
            except Exception:
                pass


def _wait(page, predicate, *, seconds: float, label: str):
    deadline = time.monotonic() + seconds
    last_url = page.url
    last_body = ""
    while time.monotonic() < deadline:
        _wake_if_needed(page)
        frame, text = _best_app_frame(page)
        last_url, last_body = page.url, text
        if frame is not None and predicate(frame, text):
            return frame, text
        page.wait_for_timeout(400)
    raise AssertionError(f"{label}_TIMEOUT url={last_url} body={last_body[:2600]!r}")


def _visible_nfl_control(frame):
    nfl_button = frame.locator("button").filter(
        has_text=re.compile(r"^\s*(?:🏈\s*)?NFL\s*$", re.I)
    )
    try:
        for index in range(nfl_button.count()):
            item = nfl_button.nth(index)
            if item.is_visible():
                return item
    except Exception:
        pass
    return None


def run(*, production_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    start_url = production_url.rstrip("/") + "/?sport=mlb&market=slate"
    result = {
        "production_url": production_url,
        "start_url": start_url,
        "status": "BLOCKED",
        "checks": {},
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=120000)
            frame, body = _wait(
                page,
                lambda f, text: (
                    "KYRE SPORTS AI" in text.upper()
                    and any(token in text for token in ("MLB Slate", "MLB slate date", "MLB Schedule V3.3"))
                ),
                seconds=150,
                label="MLB_COLD_START",
            )
            result["checks"]["mlb_cold_start"] = True
            if "canonical universal route is not registered live" in body.lower():
                raise AssertionError("cold-start canonical-route error is visible")

            top_link = frame.locator('a[href="#kyre-universal-top-anchor"]')
            top_anchor = frame.locator('[id="kyre-universal-top-anchor"]')
            if top_link.count() < 1 or top_anchor.count() < 1:
                raise AssertionError("universal Top control/anchor missing on MLB")
            if "↑ Top" not in _body(frame):
                raise AssertionError("Top label not visible on MLB")
            result["checks"]["header_mlb"] = True
            result["checks"]["top_mlb"] = True
            page.screenshot(path=str(artifacts / "01-mlb-cold-start.png"), full_page=True)

            nfl_control = _visible_nfl_control(frame)
            if nfl_control is None:
                raise AssertionError("visible NFL sport control not found")
            nfl_control.click()

            def nfl_is_sole_owner(_frame, text: str) -> bool:
                url = page.url.lower()
                nfl_ready = "sport=nfl" in url and any(
                    token in text for token in ("NFL Command Center", "NFL slate date")
                )
                mlb_gone = not any(
                    token in text for token in ("MLB Schedule V3.3", "MLB slate date", "MLB Slate")
                )
                return nfl_ready and mlb_gone

            frame, body = _wait(page, nfl_is_sole_owner, seconds=120, label="NFL_ROUTE")
            if "KYRE SPORTS AI" not in body.upper():
                raise AssertionError("KYRE SPORTS AI header missing after NFL tap")
            if frame.locator('a[href="#kyre-universal-top-anchor"]').count() < 1:
                raise AssertionError("Top control missing after NFL tap")
            if "canonical universal route is not registered live" in body.lower():
                raise AssertionError("canonical-route error visible after NFL tap")

            result["checks"].update(
                {
                    "nfl_url_owner": "sport=nfl" in page.url.lower(),
                    "nfl_body_owner": True,
                    "mlb_body_retired": True,
                    "header_nfl": True,
                    "top_nfl": True,
                }
            )
            result["final_url"] = page.url
            result["page_errors"] = page_errors
            result["status"] = "GREEN"
            page.screenshot(path=str(artifacts / "02-nfl-sole-owner.png"), full_page=True)
            print("API2_PUBLIC_MLB_HEADER_TOP_GREEN")
            print("API2_PUBLIC_NFL_SOLE_OWNER_GREEN")
            print("API2_PUBLIC_SHELL_ROUTE_TOP_GREEN")
        finally:
            (artifacts / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            browser.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=DEFAULT_URL)
    parser.add_argument("--artifact-dir", default="artifacts/api2-universal-shell-route-top-public")
    args = parser.parse_args()
    result = run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    if result.get("status") != "GREEN":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
