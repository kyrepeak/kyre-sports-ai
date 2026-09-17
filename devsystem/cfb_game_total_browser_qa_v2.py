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
RAW_EVIDENCE_LABEL = "Raw Steps 1–10 evidence"
HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
SPORTSBOOK_MARKER = "sportsbook projection influence 0.0%"
DEEP_AUDIT_LABEL = "Deep model evidence • Step 11 distribution"


class V152BrowserQAFailure(RuntimeError):
    pass


def _set_target_date(page, frame) -> tuple[str, Any]:
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
        segment.click()
        segment.press("Control+A")
        segment.fill(value)

    page.keyboard.press("Tab")
    page.keyboard.press("Escape")
    page.wait_for_timeout(2200)

    fresh_frame, _ = base._find_app_frame(page, timeout_seconds=60.0)
    combo = fresh_frame.get_by_role("combobox", name=MATCHUP_LABEL, exact=True)
    try:
        combo.wait_for(state="visible", timeout=45000)
    except Exception as exc:
        body = fresh_frame.locator("body").inner_text(timeout=5000)
        raise V152BrowserQAFailure(
            "Game Total matchup selector did not appear after setting "
            f"{TARGET_DAY}; page tail={body[-1200:]!r}"
        ) from exc
    return f"{TARGET_DAY} ({', '.join(diag)})", fresh_frame


def _choose_target_matchup(page, frame) -> tuple[str, Any]:
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
    fresh_frame, _ = base._find_app_frame(page, timeout_seconds=60.0)
    return observed, fresh_frame


def _visible(frame, testid: str):
    locator = frame.locator(f'[data-testid="{testid}"]').first
    locator.wait_for(state="visible", timeout=45000)
    return locator


def _probe_logo_url(page, src: str) -> dict[str, Any]:
    try:
        response = page.request.get(
            src,
            timeout=20000,
            fail_on_status_code=False,
        )
    except Exception as exc:
        raise V152BrowserQAFailure(
            f"logo source request failed for {src!r}: {type(exc).__name__}: {exc}"
        ) from exc

    content_type = str(response.headers.get("content-type") or "").lower()
    status = int(response.status)
    if status < 200 or status >= 400:
        raise V152BrowserQAFailure(
            f"logo source returned HTTP {status}: {src!r}"
        )
    if "image/" not in content_type:
        raise V152BrowserQAFailure(
            f"logo source is not an image: status={status} content-type={content_type!r} src={src!r}"
        )
    return {"source_status": status, "source_content_type": content_type}


def _assert_logo_loaded(page, frame, side: str) -> dict[str, Any]:
    locator = _visible(frame, f"gt152-{side}-logo")
    src = (locator.get_attribute("src") or "").strip()
    if not src:
        raise V152BrowserQAFailure(f"{side} logo src is blank")

    width = int(locator.evaluate("el => el.naturalWidth || 0"))
    source = _probe_logo_url(page, src)
    return {
        "src": src,
        "natural_width": width,
        "source_status": source["source_status"],
        "source_content_type": source["source_content_type"],
    }


def _assert_record(frame, side: str) -> str:
    value = _visible(frame, f"gt152-{side}-record").inner_text().strip()
    if value in {"", "—", "0-0"}:
        raise V152BrowserQAFailure(f"{side} record is a placeholder: {value!r}")
    return value


def _assert_compact_team_card(frame, side: str, team_name: str) -> dict[str, str]:
    card = _visible(frame, f"gt155-{side}-team-card")
    text = card.inner_text().strip()
    normalized = text.casefold()
    if team_name.casefold() not in normalized:
        raise V152BrowserQAFailure(
            f"{side} compact team card is missing {team_name!r}: {text!r}"
        )
    required_labels = ("ppg", "allowed", "recent form")
    if any(label not in normalized for label in required_labels):
        raise V152BrowserQAFailure(
            f"{side} compact team card is missing required evidence labels: {text!r}"
        )
    return {"team": team_name, "text": text}


def _open_raw_evidence(frame) -> dict[str, bool]:
    label = frame.get_by_text(RAW_EVIDENCE_LABEL, exact=False).first
    label.wait_for(state="visible", timeout=30000)
    details = label.locator("xpath=ancestor::details[1]")
    if details.count() == 0:
        raise V152BrowserQAFailure("Raw Steps 1–10 evidence drawer is missing")
    if details.get_attribute("open") is None:
        label.click()

    details.get_by_text(f"{TARGET_AWAY} • full evidence", exact=True).wait_for(
        state="visible", timeout=20000
    )
    details.get_by_text(f"{TARGET_HOME} • full evidence", exact=True).wait_for(
        state="visible", timeout=20000
    )
    details.get_by_text("Recent completed games", exact=True).first.wait_for(
        state="visible", timeout=20000
    )
    details.get_by_text("DATA SOURCE", exact=False).first.wait_for(
        state="visible", timeout=20000
    )
    return {
        "away_full_evidence_visible": True,
        "home_full_evidence_visible": True,
        "recent_games_visible": True,
        "data_source_visible": True,
    }


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

            observed_date, frame = _set_target_date(page, frame)
            matchup, frame = _choose_target_matchup(page, frame)
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
            away_logo = _assert_logo_loaded(page, frame, "away")
            home_logo = _assert_logo_loaded(page, frame, "home")
            away_record = _assert_record(frame, "away")
            home_record = _assert_record(frame, "home")
            away_team_card = _assert_compact_team_card(frame, "away", TARGET_AWAY)
            home_team_card = _assert_compact_team_card(frame, "home", TARGET_HOME)
            base._wait_for_text(frame, SPORTSBOOK_MARKER, timeout_seconds=60.0)

            deep = _deep_audit_collapsed(frame)
            raw_evidence = _open_raw_evidence(frame)

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
                "away_team_card": away_team_card,
                "home_team_card": home_team_card,
                "raw_evidence": raw_evidence,
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
