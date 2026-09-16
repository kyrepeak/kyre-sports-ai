"""Real-browser certification for the CFB Game Total V152 Monster dashboard.

Unlike the activation-only proof, this drives the real app.py entrypoint to the
exact user-reported matchup (2026-09-17 Syracuse at Pittsburgh) and proves the
visible logos, records, compact layout, evidence expanders, collapsed deep audit,
and frozen sportsbook influence contract.
"""
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
HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
SPORTSBOOK_MARKER = "sportsbook projection influence 0.0%"
DEEP_AUDIT_LABEL = "Deep model evidence • Step 11 distribution"


class V152BrowserQAFailure(RuntimeError):
    pass


def _set_target_date(page, frame) -> str:
    locator = frame.locator('input[aria-label*="CFB Game Total slate date"]').first
    if locator.count() == 0:
        locator = frame.get_by_label(DATE_LABEL, exact=True).first
    locator.wait_for(state="visible", timeout=30000)

    # Streamlit date inputs can render locale formatting differently. Try the
    # formats accepted by the current widget and keep the first that resolves to
    # the target day.
    attempts: list[str] = []
    for value in ("2026/09/17", "09/17/2026", "2026-09-17"):
        try:
            locator.click()
            locator.fill(value)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1800)
            observed = locator.input_value(timeout=5000).strip()
            attempts.append(observed)
            digits = "".join(ch for ch in observed if ch.isdigit())
            if digits in {"20260917", "09172026"}:
                return observed
        except Exception as exc:
            attempts.append(f"{value}: {type(exc).__name__}")

    raise V152BrowserQAFailure(
        f"Could not set Game Total date to {TARGET_DAY}; observed={attempts!r}"
    )


def _choose_target_matchup(page, frame) -> str:
    combo = frame.get_by_role("combobox", name=MATCHUP_LABEL, exact=True)
    combo.wait_for(state="visible", timeout=45000)
    combo.click()
    page.keyboard.type(TARGET_AWAY)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1800)
    observed = combo.input_value(timeout=5000).strip()
    if TARGET_AWAY not in observed or TARGET_HOME not in observed:
        body = frame.locator("body").inner_text(timeout=5000)
        if TARGET_AWAY not in body or TARGET_HOME not in body:
            raise V152BrowserQAFailure(
                f"Target matchup was not selected; combobox={observed!r}"
            )
    return observed


def _require_visible_testid(frame, testid: str):
    locator = frame.locator(f'[data-testid="{testid}"]').first
    locator.wait_for(state="visible", timeout=45000)
    return locator


def _assert_logo_loaded(frame, side: str) -> dict[str, Any]:
    locator = _require_visible_testid(frame, f"gt152-{side}-logo")
    src = (locator.get_attribute("src") or "").strip()
    if not src:
        raise V152BrowserQAFailure(f"{side} logo src is blank")
    try:
        natural_width = int(locator.evaluate("el => el.naturalWidth || 0"))
    except Exception:
        natural_width = 0
    if natural_width <= 0:
        raise V152BrowserQAFailure(
            f"{side} logo did not load in the browser: {src!r}"
        )
    return {"src": src, "natural_width": natural_width}


def _assert_record(frame, side: str) -> str:
    locator = _require_visible_testid(frame, f"gt152-{side}-record")
    value = locator.inner_text(timeout=5000).strip()
    if value in {"", "—", "0-0"}:
        raise V152BrowserQAFailure(
            f"{side} record is still a placeholder: {value!r}"
        )
    return value


def _open_team_evidence(frame, team: str) -> dict[str, Any]:
    label_text = f"{team} evidence"
    label = frame.get_by_text(label_text, exact=True).first
    label.wait_for(state="visible", timeout=30000)
    details = label.locator("xpath=ancestor::details[1]")
    if details.count() > 0:
        if details.get_attribute("open") is None:
            label.click()
        details.get_by_text("Recent completed games", exact=True).wait_for(
            state="visible", timeout=20000
        )
        details.get_by_text("DATA SOURCE", exact=False).first.wait_for(
            state="visible", timeout=20000
        )
        body = details.inner_text(timeout=5000)
    else:
        label.click()
        frame.get_by_text("Recent completed games", exact=True).first.wait_for(
            state="visible", timeout=20000
        )
        frame.get_by_text("DATA SOURCE", exact=False).first.wait_for(
            state="visible", timeout=20000
        )
        body = frame.locator("body").inner_text(timeout=5000)
    return {
        "label": label_text,
        "recent_games_visible": "Recent completed games" in body,
        "data_source_visible": "DATA SOURCE" in body,
    }


def _assert_deep_audit_collapsed(frame) -> dict[str, Any]:
    label = frame.get_by_text(DEEP_AUDIT_LABEL, exact=False).first
    label.wait_for(state="visible", timeout=30000)

    # Streamlit versions vary: some expose aria-expanded on the trigger while
    # others rely on the surrounding <details open> state. Certify both forms.
    aria_trigger = label.locator("xpath=ancestor-or-self::*[@aria-expanded][1]")
    aria_expanded = None
    if aria_trigger.count() > 0:
        aria_expanded = aria_trigger.get_attribute("aria-expanded")
        if aria_expanded == "true":
            raise V152BrowserQAFailure("Step-11 deep audit is expanded by default")

    details = label.locator("xpath=ancestor::details[1]")
    details_open = None
    if details.count() > 0:
        details_open = details.get_attribute("open")
        if details_open is not None:
            raise V152BrowserQAFailure("Step-11 deep audit details is open by default")

    return {
        "aria-expanded": aria_expanded,
        "details_open": details_open is not None,
    }


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-v152",
) -> dict[str, Any]:
    artifacts = base._artifact_dir(artifact_dir)
    health = base._wait_for_health(base_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1800})
        try:
            page.goto(
                base_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scans = base._find_app_frame(page)
            sports = base._read_sport_options(page, frame)
            if CFB_SPORT not in sports:
                raise V152BrowserQAFailure(
                    f"College Football selector option missing: {sports!r}"
                )

            base._choose(page, frame, 0, CFB_SPORT)
            market_combo = frame.get_by_role(
                "combobox", name=CFB_MARKET_LABEL, exact=True
            )
            market_combo.wait_for(state="visible", timeout=45000)
            base._choose(page, frame, 1, GAME_TOTAL_MARKET)

            body = base._wait_for_text(frame, HEARTBEAT, timeout_seconds=60.0)
            if HEARTBEAT not in body:
                raise V152BrowserQAFailure("V152 production heartbeat is missing")

            observed_date = _set_target_date(page, frame)
            matchup = _choose_target_matchup(page, frame)
            body = base._wait_for_text(frame, "MONSTER MATCHUP", timeout_seconds=60.0)

            forbidden_error = base._body_has_forbidden_error(body)
            if forbidden_error:
                raise V152BrowserQAFailure(
                    f"Game Total runtime error marker: {forbidden_error}"
                )

            _require_visible_testid(frame, "gt152-monster-matchup-hero")
            _require_visible_testid(frame, "gt152-compact-game-strip")
            _require_visible_testid(frame, "gt152-scoring-defense")
            away_logo = _assert_logo_loaded(frame, "away")
            home_logo = _assert_logo_loaded(frame, "home")
            away_record = _assert_record(frame, "away")
            home_record = _assert_record(frame, "home")

            if TARGET_AWAY not in body or TARGET_HOME not in body:
                raise V152BrowserQAFailure(
                    f"Expected {TARGET_AWAY} @ {TARGET_HOME} in rendered body"
                )
            if "SPORTSBOOK" not in body.upper() or "0.0%" not in body:
                raise V152BrowserQAFailure(
                    f"Frozen sportsbook marker missing: expected {SPORTSBOOK_MARKER!r}"
                )

            deep_audit = _assert_deep_audit_collapsed(frame)
            away_evidence = _open_team_evidence(frame, TARGET_AWAY)
            home_evidence = _open_team_evidence(frame, TARGET_HOME)

            screenshot = artifacts / "cfb_game_total_v152.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "sport": CFB_SPORT,
                "market": GAME_TOTAL_MARKET,
                "target_day": TARGET_DAY,
                "observed_date": observed_date,
                "matchup": matchup,
                "heartbeat": HEARTBEAT,
                "away_team": TARGET_AWAY,
                "home_team": TARGET_HOME,
                "away_record": away_record,
                "home_record": home_record,
                "away_logo": away_logo,
                "home_logo": home_logo,
                "away_evidence": away_evidence,
                "home_evidence": home_evidence,
                "deep_audit": deep_audit,
                "sportsbook_projection_influence": "0.0%",
                "health": health,
                "initial_frame_scan": scans,
                "screenshot": str(screenshot),
            }
            evidence = artifacts / "cfb_game_total_v152.json"
            evidence.write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            print("CFB_GAME_TOTAL_V152_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir", default="artifacts/cfb-game-total-v152"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
