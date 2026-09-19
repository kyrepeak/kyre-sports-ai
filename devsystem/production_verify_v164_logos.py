"""Production verification for CFB Game Total V164 exact team logos.

V164 is presentation-only. The existing V5 production workflow remains the
separate required V163 persistence gate. This verifier proves only the additive
V164 exact ESPN team-logo rendering in the live Streamlit deployment, avoiding
duplicate concurrent browser certification against the same app process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import production_verify_v5 as v163
from devsystem import production_verify_v1 as base

CERT_DATE = "2026-09-18"
CERT_EVENT_ID = "401858226"
AWAY_TEAM = "Miami"
HOME_TEAM = "Wake Forest"
AWAY_TEAM_ID = "2390"
HOME_TEAM_ID = "154"
REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE"
REQUIRED_PATCH_MARKER = "CFB_GAME_TOTAL_V164_BLANK_EVENT_ID_HANDOFF_PATCH_ACTIVE"
REQUIRED_STEP1_MARKER = "CFB_GAME_TOTAL_STEP1_TEAM_IDENTITY_ACCORDION_ACTIVE"
REQUIRED_STEP1_PROFILE_MARKER = "CFB_GAME_TOTAL_STEP1_FAST_EXACT_PROFILE_ACTIVE"
REQUIRED_STEP2_MARKER = "CFB_GAME_TOTAL_STEP2_PERFORMANCE_PROFILE_V2_ACTIVE"
REQUIRED_STEP3_MARKER = "CFB_GAME_TOTAL_STEP3_CURRENT_FORM_OPPONENT_QUALITY_ACTIVE"
REQUIRED_STEP4_MARKER = "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE"
REQUIRED_STEP4_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP4_MULTISOURCE_FULL_COVERAGE_ACTIVE"


class ProductionVerificationV164Failure(RuntimeError):
    pass


def _image_state(locator) -> dict:
    return locator.evaluate(
        """img => ({
            src: img.currentSrc || img.src || "",
            complete: Boolean(img.complete),
            naturalWidth: Number(img.naturalWidth || 0),
            naturalHeight: Number(img.naturalHeight || 0)
        })"""
    )


def _wait_image_state(locator, timeout_ms: int = 15000) -> dict:
    """Wait for the external logo request to settle, then return strict image state."""
    locator.wait_for(state="attached", timeout=timeout_ms)
    return locator.evaluate(
        """(img, timeout) => new Promise((resolve) => {
            const snapshot = () => ({
                src: img.currentSrc || img.src || "",
                complete: Boolean(img.complete),
                naturalWidth: Number(img.naturalWidth || 0),
                naturalHeight: Number(img.naturalHeight || 0)
            });
            if (img.complete) {
                resolve(snapshot());
                return;
            }
            let done = false;
            const finish = () => {
                if (done) return;
                done = true;
                resolve(snapshot());
            };
            img.addEventListener("load", finish, {once: true});
            img.addEventListener("error", finish, {once: true});
            setTimeout(finish, timeout);
        })""",
        timeout_ms,
    )


def _assert_exact_pair(
    frame,
    selector: str,
    label: str,
    *,
    render_timeout_ms: int = 30000,
) -> list[dict]:
    """Wait for the full Streamlit surface before enforcing the exact two-logo contract."""
    images = frame.locator(selector)
    try:
        images.nth(0).wait_for(state="attached", timeout=render_timeout_ms)
        images.nth(1).wait_for(state="attached", timeout=render_timeout_ms)
    except Exception as exc:
        raise ProductionVerificationV164Failure(
            f"{label} timed out waiting for two exact logo images; found {images.count()}"
        ) from exc
    if images.count() != 2:
        raise ProductionVerificationV164Failure(
            f"{label} expected two exact logo images; found {images.count()}"
        )
    states = [_wait_image_state(images.nth(i)) for i in range(images.count())]
    urls = [str(row["src"]) for row in states]
    for team_id in (AWAY_TEAM_ID, HOME_TEAM_ID):
        suffix = f"/{team_id}.png"
        if not any(url.endswith(suffix) for url in urls):
            raise ProductionVerificationV164Failure(
                f"{label} missing ESPN team logo {suffix}: {urls}"
            )
    for row in states:
        if not row["complete"] or row["naturalWidth"] <= 0 or row["naturalHeight"] <= 0:
            raise ProductionVerificationV164Failure(
                f"{label} image failed to load: {row}"
            )
    return states



def _wait_for_v164_patch_deployment(
    page,
    *,
    timeout_seconds: float = 240.0,
):
    """Reload until the live app proves this exact logo patch is deployed."""
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    last_scans: list[dict] = []
    last_error = ""
    while time.monotonic() < deadline:
        try:
            frame, body, scans = v163._wait_for_top_level_selection(
                page,
                CERT_EVENT_ID,
                timeout_seconds=45.0,
            )
            last_body = body
            last_scans = scans
            last_error = ""
            dom_text = str(frame.locator("body").text_content() or body)
            if (
                REQUIRED_HEARTBEAT in dom_text
                and REQUIRED_PATCH_MARKER in dom_text
                and REQUIRED_STEP1_MARKER in dom_text
                and REQUIRED_STEP1_PROFILE_MARKER in dom_text
                and REQUIRED_STEP2_MARKER in dom_text
                and REQUIRED_STEP3_MARKER in dom_text
                and REQUIRED_STEP4_MARKER in dom_text
                and REQUIRED_STEP4_DEPLOYMENT_MARKER in dom_text
            ):
                return frame, dom_text, scans
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise ProductionVerificationV164Failure(
        "V164 logo proof timed out waiting for the current Streamlit patch: "
        f"required_marker={REQUIRED_PATCH_MARKER!r} "
        f"required_step1_marker={REQUIRED_STEP1_MARKER!r} "
        f"required_step1_profile_marker={REQUIRED_STEP1_PROFILE_MARKER!r} "
        f"required_step2_marker={REQUIRED_STEP2_MARKER!r} "
        f"required_step3_marker={REQUIRED_STEP3_MARKER!r} "
        f"required_step4_marker={REQUIRED_STEP4_MARKER!r} "
        f"required_step4_deployment_marker={REQUIRED_STEP4_DEPLOYMENT_MARKER!r} "
        f"required_step3_marker={REQUIRED_STEP3_MARKER!r} "
        f"last_error={last_error!r} scans={last_scans!r} "
        f"body_start={last_body[:500]!r}"
    )



def _assert_step1_identity(frame) -> dict:
    step = frame.locator('details[data-testid="gt157-step-1"]')
    try:
        step.wait_for(state="attached", timeout=30000)
    except Exception as exc:
        raise ProductionVerificationV164Failure(
            "Step 1 timed out waiting for the connected accordion to render"
        ) from exc
    if step.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 1 expected one connected accordion; found {step.count()}"
        )
    if step.get_attribute("open") is None:
        raise ProductionVerificationV164Failure("Step 1 must render expanded by default")

    away = frame.locator('[data-testid="gt165-step1-away"]')
    home = frame.locator('[data-testid="gt165-step1-home"]')
    if away.count() != 1 or home.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 1 expected two team identity cards; away={away.count()} home={home.count()}"
        )

    text = step.inner_text()
    required_text = (
        "Team Identity",
        AWAY_TEAM,
        HOME_TEAM,
        "Mascot",
        "Conference",
        "FBS/FCS",
        "Record",
        "Rank",
        "Coach",
        "Home/Away",
        "Season",
        "Identity Verified",
    )
    missing = [label for label in required_text if label not in text]
    if missing:
        raise ProductionVerificationV164Failure(
            f"Step 1 missing required visible labels/content: {missing}"
        )
    if "Unavailable" in text or "unavailable" in text or "Needs data:" in text:
        raise ProductionVerificationV164Failure(
            f"Step 1 is not complete for the certified matchup: {text[:1200]}"
        )

    state = step.locator(".gt159-state").first.inner_text().strip()
    if state != "READY":
        raise ProductionVerificationV164Failure(
            f"Step 1 expected READY but rendered {state!r}"
        )

    verified = step.locator(".gt165-verify b")
    verified_text = [verified.nth(i).inner_text().strip() for i in range(verified.count())]
    if verified.count() != 2 or any("IDENTITY VERIFIED" not in value for value in verified_text):
        raise ProductionVerificationV164Failure(
            f"Step 1 identity verification badges are incomplete: {verified_text}"
        )

    logos = _assert_exact_pair(frame, "img.gt165-idlogo", "Step 1 identity")
    return {
        "status": state,
        "text": text,
        "verification_badges": verified_text,
        "logos": logos,
    }



def _assert_step2_performance_profile(frame) -> dict:
    step = frame.locator('details[data-testid="gt157-step-2"]')
    try:
        step.wait_for(state="attached", timeout=30000)
    except Exception as exc:
        raise ProductionVerificationV164Failure(
            "Step 2 timed out waiting for the Team Performance Profile to render"
        ) from exc
    if step.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 2 expected one connected accordion; found {step.count()}"
        )
    if step.get_attribute("open") is None:
        raise ProductionVerificationV164Failure(
            "Step 2 Team Performance Profile must render expanded by default"
        )

    away = frame.locator('[data-testid="gt167-step2-away"]')
    home = frame.locator('[data-testid="gt167-step2-home"]')
    insights = frame.locator('[data-testid="gt167-step2-insights"]')
    summary = frame.locator('[data-testid="gt167-step2-summary"]')
    if away.count() != 1 or home.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 2 expected two universal team cards; away={away.count()} home={home.count()}"
        )
    if insights.count() != 1 or summary.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 2 missing insight/summary surfaces; insights={insights.count()} summary={summary.count()}"
        )

    state = str(step.get_attribute("data-step2-state") or "").strip().upper()
    text = step.inner_text()
    if state != "READY":
        raise ProductionVerificationV164Failure(
            "Step 2 certified matchup must be fully READY after certified profile "
            f"and drive hydration: state={state!r} live_text={text[:2400]!r}"
        )
    required_text = (
        "Team Performance Profile",
        AWAY_TEAM,
        HOME_TEAM,
        "SAMPLE GAMES",
        "POINTS / GAME",
        "ALLOWED / GAME",
        "YARDS / PLAY",
        "PTS / DRIVE",
        "OFF EFF RANK",
        "YPP ALLOWED",
        "PTS/DRIVE ALLOWED",
        "DEF EFF RANK",
        "POINT DIFF / GAME",
        "HOME/AWAY SPLIT",
        "RECENT FORM",
        "PROFILE EDGE",
        "WHAT STEP 2 TELLS YOU",
        "STEP 2 SUMMARY",
    )
    live_text_upper = text.upper()
    missing = [label for label in required_text if label.upper() not in live_text_upper]
    if missing:
        raise ProductionVerificationV164Failure(
            f"Step 2 missing required universal performance-profile content: {missing}"
        )

    metric_cards = step.locator(".gt167-metric")
    metric_values = [
        str(metric_cards.nth(i).locator("b").inner_text() or "").strip()
        for i in range(metric_cards.count())
    ]
    blank_metric_values = [
        value for value in metric_values
        if value.strip() in {"", "—", "-"}
    ]
    if blank_metric_values:
        raise ProductionVerificationV164Failure(
            "Step 2 READY contains blank universal metric values: "
            f"{blank_metric_values}"
        )
    if "DATA STILL LIMITED:" in live_text_upper:
        raise ProductionVerificationV164Failure(
            "Step 2 READY must not render a Data still limited warning"
        )

    for side_name, card in (("away", away), ("home", home)):
        record_value = str(
            card.locator(".gt167-record b").inner_text() or ""
        ).strip()
        sample_value = str(
            card.locator(".gt167-metric").nth(0).locator("b").inner_text() or ""
        ).strip()
        try:
            sample_games = int(float(sample_value))
        except (TypeError, ValueError):
            sample_games = 0
        if sample_games > 0 and record_value in {"", "—", "-", "0-0", "0-0-0"}:
            raise ProductionVerificationV164Failure(
                f"Step 2 {side_name} READY record is stale/empty despite "
                f"{sample_games} completed sample games: record={record_value!r}"
            )

    logos = _assert_exact_pair(frame, "img.gt167-logo", "Step 2 performance profile")
    return {
        "status": state,
        "coverage": coverage,
        "limited_tiles": limited_tiles,
        "text": text,
        "logos": logos,
        "insight_cards": insights.locator(".gt167-insight").count(),
        "metric_cards": step.locator(".gt167-metric").count(),
    }



def _assert_step3_current_form(frame) -> dict:
    step = frame.locator('details[data-testid="gt157-step-3"]')
    try:
        step.wait_for(state="attached", timeout=30000)
    except Exception as exc:
        raise ProductionVerificationV164Failure(
            "Step 3 timed out waiting for Current Form & Opponent Quality"
        ) from exc
    if step.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 3 expected one connected accordion; found {step.count()}"
        )
    if step.get_attribute("open") is None:
        raise ProductionVerificationV164Failure(
            "Step 3 Current Form & Opponent Quality must render expanded by default"
        )

    away = frame.locator('[data-testid="gt168-step3-away"]')
    home = frame.locator('[data-testid="gt168-step3-home"]')
    comparison = frame.locator('[data-testid="gt168-step3-comparison"]')
    takeaways = frame.locator('[data-testid="gt168-step3-takeaways"]')
    edge = frame.locator('[data-testid="gt168-step3-edge"]')
    if away.count() != 1 or home.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 3 expected two universal form cards; away={away.count()} home={home.count()}"
        )
    if comparison.count() != 1 or takeaways.count() != 1 or edge.count() != 1:
        raise ProductionVerificationV164Failure(
            "Step 3 missing comparison/takeaway/form-edge surfaces: "
            f"comparison={comparison.count()} takeaways={takeaways.count()} edge={edge.count()}"
        )

    state = str(step.get_attribute("data-step3-state") or "").strip().upper()
    text = step.inner_text()
    diag_attr = str(step.get_attribute("data-step3-diag") or "")
    if state != "READY":
        raise ProductionVerificationV164Failure(
            "Step 3 certified matchup must be fully READY after current-form and "
            f"opponent-quality hydration: state={state!r} "
            f"diag={diag_attr[:9000]!r} live_text={text[:2400]!r}"
        )

    required_text = (
        "Current Form & Opponent Quality",
        AWAY_TEAM,
        HOME_TEAM,
        "Last 5 Games",
        "Recent Averages",
        "Opponent Quality",
        "FORM COMPARISON",
        "TREND",
        "KEY TAKEAWAYS",
        "FORM EDGE",
        "Avg PPG",
        "Avg Allowed",
        "Avg Diff",
    )
    live_text_upper = text.upper()
    missing = [label for label in required_text if label.upper() not in live_text_upper]
    if missing:
        raise ProductionVerificationV164Failure(
            f"Step 3 missing required universal current-form content: {missing}"
        )

    if "INSUFFICIENT SAMPLE" in live_text_upper:
        raise ProductionVerificationV164Failure(
            "Step 3 still exposes obsolete 'Insufficient sample' trend wording"
        )

    game_rows_by_side: dict[str, int] = {}
    opponent_quality_values: dict[str, list[str]] = {}
    for side_name, card in (("away", away), ("home", home)):
        game_rows = card.locator(".gt168-table tbody tr")
        game_count = game_rows.count()
        game_rows_by_side[side_name] = game_count
        if game_count < 2:
            raise ProductionVerificationV164Failure(
                f"Step 3 {side_name} card expected at least 2 verified completed-game "
                f"rows for the certified completed-game sample; found {game_count}"
            )
        if "NO VERIFIED COMPLETED-GAME ROWS" in card.inner_text().upper():
            raise ProductionVerificationV164Failure(
                f"Step 3 {side_name} card rendered the empty completed-game fallback"
            )

        quality_rows = card.locator(".gt168-opp-row")
        if quality_rows.count() != 5:
            raise ProductionVerificationV164Failure(
                f"Step 3 {side_name} Opponent Quality expected 5 rows; "
                f"found {quality_rows.count()}"
            )
        values = [
            str(quality_rows.nth(i).locator("b").inner_text() or "").strip()
            for i in range(quality_rows.count())
        ]
        opponent_quality_values[side_name] = values

    status_reasons = step.locator(
        '[data-testid="gt168-step3-status-reason"]'
    )
    blank_values = {
        side_name: [
            value for value in values
            if value.strip() in {"", "—", "-"}
        ]
        for side_name, values in opponent_quality_values.items()
    }
    if any(blank_values.values()):
        raise ProductionVerificationV164Failure(
            f"Step 3 READY contains blank Opponent Quality values: {blank_values}"
        )
    if status_reasons.count() != 0:
        raise ProductionVerificationV164Failure(
            "Step 3 READY must not render a CHECK/DATA LIMITED reason"
        )

    logos = _assert_exact_pair(frame, "img.gt168-logo", "Step 3 current form")
    return {
        "status": state,
        "text": text,
        "logos": logos,
        "game_rows_by_side": game_rows_by_side,
        "opponent_quality_values": opponent_quality_values,
        "opponent_quality_rows": step.locator(".gt168-opp-row").count(),
        "status_reason_rows": status_reasons.count(),
        "takeaway_rows": takeaways.locator("div").count(),
    }




def _assert_step4_matchup(frame) -> dict:
    """Verify the active V165 Step 4 surface without weakening frozen logo checks."""
    step = frame.locator('details[data-testid="gt157-step-4"]')
    try:
        step.wait_for(state="attached", timeout=30000)
    except Exception as exc:
        raise ProductionVerificationV164Failure(
            "Step 4 timed out waiting for V165 Matchup to render"
        ) from exc
    if step.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 4 expected one connected accordion; found {step.count()}"
        )
    if step.get_attribute("open") is None:
        raise ProductionVerificationV164Failure(
            "Step 4 V165 Matchup must render expanded by default"
        )

    away = frame.locator('[data-testid="gt165-step4-away-off-home-def"]')
    home = frame.locator('[data-testid="gt165-step4-home-off-away-def"]')
    source_integrity = frame.locator('[data-testid="gt165-step4-source-integrity"]')
    advanced_integrity = frame.locator('[data-testid="gt165-step4-advanced-integrity"]')
    if away.count() != 1 or home.count() != 1:
        raise ProductionVerificationV164Failure(
            f"Step 4 expected two V165 directional matchup cards; away={away.count()} home={home.count()}"
        )
    if source_integrity.count() != 1 or advanced_integrity.count() != 1:
        raise ProductionVerificationV164Failure(
            "Step 4 missing V165 source-integrity or advanced-integrity surface"
        )

    state = str(step.get_attribute("data-step4-state") or "").strip().upper()
    if state != "READY":
        raise ProductionVerificationV164Failure(
            f"Step 4 certified matchup must be fully READY: state={state!r}"
        )

    coverage = str(step.get_attribute("data-step4-coverage") or "").strip()
    if coverage != "100":
        raise ProductionVerificationV164Failure(
            f"Step 4 certified matchup must show 100% visible coverage: coverage={coverage!r}"
        )

    limited_tiles = step.locator(".gt165-metric.limited").count()
    if limited_tiles != 0:
        raise ProductionVerificationV164Failure(
            f"Step 4 READY still contains limited matchup tiles: {limited_tiles}"
        )

    text = step.inner_text()
    required_text = (
        "Matchup",
        AWAY_TEAM,
        HOME_TEAM,
        "Off vs Def",
        "Pass Yds/G",
        "Rush Yds/G",
        "3rd Down",
        "Red Zone",
        "Sack Matchup",
        "Turnover Pressure",
        "BIGGEST EDGE",
        "BIGGEST RISK",
        "O/U IMPACT",
        "VERIFIED MATCHUP DATA",
        "ADVANCED-METRIC INTEGRITY",
    )
    live_text_upper = str(text or "").upper()
    missing = [label for label in required_text if label.upper() not in live_text_upper]
    if missing:
        raise ProductionVerificationV164Failure(
            f"Step 4 missing required V165 matchup content: {missing}"
        )
    if "VISIBLE MATCHUP COVERAGE: 100%" not in live_text_upper:
        raise ProductionVerificationV164Failure(
            "Step 4 source-integrity card does not prove 100% visible coverage"
        )
    if "CFBSTATS" not in live_text_upper and "MULTI-SOURCE" not in live_text_upper:
        raise ProductionVerificationV164Failure(
            "Step 4 source-integrity card does not prove the multi-source fallback path"
        )

    logos = _assert_exact_pair(frame, "img.gt165-logo", "Step 4 V165 matchup")
    return {
        "status": state,
        "coverage": coverage,
        "limited_tiles": limited_tiles,
        "text": text,
        "logos": logos,
        "directional_cards": 2,
        "source_integrity": source_integrity.count(),
        "advanced_integrity": advanced_integrity.count(),
        "v165_step4_verified": True,
    }

def verify_live_v164(
    streamlit_url: str,
    *,
    artifact_dir: str | Path = "artifacts/production-v164-logos",
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    query = urlencode(
        {
            v163.ROUTE_QUERY_SPORT: v163.CFB_SPORT,
            v163.ROUTE_QUERY_MARKET: v163.GAME_TOTAL_MARKET,
            v163.DATE_QUERY_KEY: CERT_DATE,
            v163.EVENT_QUERY_KEY: CERT_EVENT_ID,
        }
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/?" + query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, scans = _wait_for_v164_patch_deployment(page)
            if REQUIRED_HEARTBEAT not in body:
                raise ProductionVerificationV164Failure(
                    f"missing V164 production heartbeat: {REQUIRED_HEARTBEAT}"
                )
            if REQUIRED_PATCH_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing current V164 logo patch marker: {REQUIRED_PATCH_MARKER}"
                )
            if REQUIRED_STEP1_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing Step 1 production marker: {REQUIRED_STEP1_MARKER}"
                )
            if REQUIRED_STEP1_PROFILE_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing Step 1 exact-profile marker: {REQUIRED_STEP1_PROFILE_MARKER}"
                )
            if REQUIRED_STEP2_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing Step 2 performance-profile marker: {REQUIRED_STEP2_MARKER}"
                )
            if REQUIRED_STEP3_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing Step 3 current-form marker: {REQUIRED_STEP3_MARKER}"
                )
            if REQUIRED_STEP4_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing Step 4 matchup marker: {REQUIRED_STEP4_MARKER}"
                )
            if REQUIRED_STEP3_MARKER not in body:
                raise ProductionVerificationV164Failure(
                    f"missing Step 3 current-form marker: {REQUIRED_STEP3_MARKER}"
                )
            if AWAY_TEAM not in body or HOME_TEAM not in body:
                raise ProductionVerificationV164Failure(
                    f"certified matchup not visible: {AWAY_TEAM} @ {HOME_TEAM}"
                )
            event_id = v163._event_from_url(page.url)
            if event_id != CERT_EVENT_ID:
                raise ProductionVerificationV164Failure(
                    f"certified event did not persist: expected={CERT_EVENT_ID!r} "
                    f"actual={event_id!r}"
                )

            header = _assert_exact_pair(frame, "img.gt159-logo", "matchup header")
            evidence = _assert_exact_pair(
                frame,
                "img.gt160-evidence-logo",
                "team evidence",
            )
            step1 = _assert_step1_identity(frame)
            step2 = _assert_step2_performance_profile(frame)
            step3 = _assert_step3_current_form(frame)
            step4 = _assert_step4_matchup(frame)

            screenshot = artifacts / "production_cfb_game_total_v164_logos_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "date": CERT_DATE,
                "event_id": event_id,
                "away_team": AWAY_TEAM,
                "away_team_id": AWAY_TEAM_ID,
                "home_team": HOME_TEAM,
                "home_team_id": HOME_TEAM_ID,
                "header_logos": header,
                "evidence_logos": evidence,
                "step1_team_identity": step1,
                "step2_team_performance_profile": step2,
                "step3_current_form_opponent_quality": step3,
                "step4_matchup": step4,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
            (artifacts / "production_v164_logo_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return result
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    targets = base._load_targets()
    parser.add_argument(
        "--streamlit-url",
        default=str(targets["streamlit"]["url"]).rstrip("/"),
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-v164-logos",
    )
    args = parser.parse_args()

    logos = verify_live_v164(
        args.streamlit_url,
        artifact_dir=args.artifact_dir,
    )
    result = {
        "status": "GREEN",
        "required_separate_gate": "DevSystem production verification V5",
        "v164_exact_team_logos": logos,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    print("CFB_GAME_TOTAL_V164_PRODUCTION_LOGOS_GREEN")


if __name__ == "__main__":
    main()
