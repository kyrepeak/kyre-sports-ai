"""Real-browser certification for the CFB Game Total V152 dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CFB_MARKET_LABEL = "🎯 CFB Market"
DATE_LABEL = "📅 CFB Game Total slate date"
MATCHUP_LABEL = "🏟️ Game Total matchup"
TARGET_DAY = "2026-09-17"
TARGET_AWAY = "Syracuse"
TARGET_HOME = "Pittsburgh"
AWAY_EVIDENCE_LABEL = "Syracuse evidence"
HOME_EVIDENCE_LABEL = "Pittsburgh evidence"
HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
DEEP_AUDIT_LABEL = "Deep model evidence • Step 11 distribution"


class V152BrowserQAFailure(RuntimeError):
    pass


def _set_target_date(page, frame) -> str:
    widget = frame.get_by_test_id("stDateInput").filter(has_text=DATE_LABEL).first
    if widget.count() == 0:
        widget = frame.get_by_test_id("stDateInput").first
    widget.wait_for(state="visible", timeout=30000)

    field = widget.get_by_test_id("stDateInputField")
    if field.count() == 0:
        raise V152BrowserQAFailure("Streamlit segmented date field is missing")

    spinbuttons = field.get_by_role("spinbutton")
    if spinbuttons.count() != 3:
        raise V152BrowserQAFailure(
            f"Expected 3 Streamlit date segments, found {spinbuttons.count()}"
        )

    fallback = ("2026", "09", "17")
    semantic_values = {"year": "2026", "month": "09", "day": "17"}
    diag: list[str] = []
    for i in range(3):
        segment = spinbuttons.nth(i)
        semantic = " ".join(
            value
            for value in (
                segment.get_attribute("aria-label"),
                segment.get_attribute("placeholder"),
                segment.get_attribute("data-segment"),
            )
            if value
        ).lower()
        value = next(
            (part for label, part in semantic_values.items() if label in semantic),
            fallback[i],
        )
        diag.append(f"{i}:{semantic or 'unlabeled'}->{value}")
        segment.press_sequentially(value)

    page.keyboard.press("Escape")
    page.wait_for_timeout(1800)
    frame.get_by_role("combobox", name=MATCHUP_LABEL, exact=True).wait_for(
        state="visible", timeout=45000
    )
    return f"{TARGET_DAY} ({', '.join(diag)})"


def _choose_target_matchup(page, frame) -> str:
    combo = frame.get_by_role("combobox", name=MATCHUP_LABEL, exact=True)
    combo.wait_for(state="visible", timeout=45000)
    combo.click()
    page.keyboard.type(TARGET_AWAY)
    page.keyboard.press("Enter")
    observed = combo.input_value(timeout=5000).strip()
    if TARGET_AWAY not in observed or TARGET_HOME not in observed:
        raise V152BrowserQAFailure(
            f"Target matchup was not selected; combobox={observed!r}"
        )
    return observed


def _visible(frame, testid: str):
    locator = frame.locator(f'[data-testid="{testid}"]').first
    locator.wait_for(state="visible", timeout=45000)
    return locator


def _assert_logo_loaded(frame, side: str) -> dict[str, Any]:
    locator = _visible(frame, f"gt152-{side}-logo")
    src = (locator.get_attribute("src") or "").strip()
    width = int(locator.evaluate("el => el.naturalWidth || 0"))
    if not src or width <= 0:
        raise V152BrowserQAFailure(f"{side} logo did not load: {src!r}")
    return {"src": src, "natural_width": width}


def _assert_record(frame, side: str) -> str:
    value = _visible(frame, f"gt152-{side}-record").inner_text().strip()
    if value in {"", "—", "0-0"}:
        raise V152BrowserQAFailure(f"{side} record is a placeholder: {value!r}")
    return value


def _open_evidence(frame, label_text: str) -> dict[str, bool]:
    label = frame.get_by_text(label_text, exact=True).first
    label.wait_for(state="visible", timeout=30000)
    details = label.locator("xpath=ancestor::details[1]")
    if details.count() == 0:
        raise V152BrowserQAFailure(f"Evidence expander missing: {label_text}")
    if details.get_attribute("open") is None:
        label.click()
    details.get_by_text("Recent completed games", exact=True).wait_for(
        state="visible", timeout=20000
    )
    details.get_by_text("DATA SOURCE", exact=False).first.wait_for(
        state="visible", timeout=20000
    )
    return {"recent_games_visible": True, "data_source_visible": True}


def _deep_audit_collapsed(frame) -> dict[str, Any]:
    label = frame.get_by_text(DEEP_AUDIT_LABEL, exact=False).first
    label.wait_for(state="visible", timeout=30000)
    details = label.locator("xpath=ancestor::details[1]")
    aria_expanded = label.get_attribute("aria-expanded")
    if details.count() and details.get_attribute("open") is not None:
        raise V152BrowserQAFailure("Step-11 deep audit is expanded by default")
    if aria_expanded == "true":
        raise V152BrowserQAFailure("Step-11 deep audit aria-expanded=true")
    return {"aria-expanded": aria_expanded, "details_open": False}


def run(*, base_url: str = base.DEFAULT_BASE_URL, artifact_dir: str | Path = "artifacts/cfb-game-total-v152") -> dict[str, Any]:
    artifacts = base._artifact_dir(artifact_dir)
    health = base._wait_for_health(base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1800})
        try:
            page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120000)
            frame, scans = base._find_app_frame(page)
            sports = base._read_sport_options(page, frame)
            if CFB_SPORT not in sports:
                raise V152BrowserQAFailure(f"College Football missing: {sports!r}")
            base._choose(page, frame, 0, CFB_SPORT)
            frame.get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True).wait_for(state="visible", timeout=45000)
            base._choose(page, frame, 1, GAME_TOTAL_MARKET)
            body = base._wait_for_text(frame, HEARTBEAT, timeout_seconds=60.0)
            if HEARTBEAT not in body:
                raise V152BrowserQAFailure("V152 production heartbeat is missing")

            observed_date = _set_target_date(page, frame)
            matchup = _choose_target_matchup(page, frame)
            body = base._wait_for_text(frame, "MONSTER MATCHUP", timeout_seconds=60.0)
            if TARGET_AWAY not in body or TARGET_HOME not in body:
                raise V152BrowserQAFailure(
                    f"Rendered Monster matchup missing {TARGET_AWAY} or {TARGET_HOME}"
                )
            forbidden = base._body_has_forbidden_error(body)
            if forbidden:
                raise V152BrowserQAFailure(f"Runtime error marker: {forbidden}")

            _visible(frame, "gt152-monster-matchup-hero")
            _visible(frame, "gt152-compact-game-strip")
            _visible(frame, "gt152-scoring-defense")
            away_logo = _assert_logo_loaded(frame, "away")
            home_logo = _assert_logo_loaded(frame, "home")
            away_record = _assert_record(frame, "away")
            home_record = _assert_record(frame, "home")
            if "SPORTSBOOK" not in body.upper() or "0.0%" not in body:
                raise V152BrowserQAFailure("SPORTSBOOK projection influence 0.0% marker missing")

            deep = _deep_audit_collapsed(frame)
            away_evidence = _open_evidence(frame, AWAY_EVIDENCE_LABEL)
            home_evidence = _open_evidence(frame, HOME_EVIDENCE_LABEL)

            screenshot = artifacts / "cfb_game_total_v152.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "target_day": TARGET_DAY,
                "observed_date": observed_date,
                "matchup": matchup,
                "away_record": away_record,
                "home_record": home_record,
                "away_logo": away_logo,
                "home_logo": home_logo,
                "away_evidence": away_evidence,
                "home_evidence": home_evidence,
                "deep_audit": deep,
                "sportsbook_projection_influence": "0.0%",
                "health": health,
                "initial_frame_scan": scans,
                "screenshot": str(screenshot),
            }
            evidence = artifacts / "cfb_game_total_v152.json"
            evidence.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            print("CFB_GAME_TOTAL_V152_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/cfb-game-total-v152")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
