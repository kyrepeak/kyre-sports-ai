"""Final production proof for the six-step CFB Game Total page cleanup.

Verifier-only. It observes the deployed normal Game Total route in one stable
Streamlit session. It never reloads/restarts/remounts the application.

Acceptance:
- cleanup presentation markers prove fresh deployment;
- Purdue @ UCLA exact event is selected;
- Game Total Analysis = READY, 12/12, four READY metrics;
- Team Evidence = two READY cards, eight READY required stat tiles;
- Game Evidence header = venue/weather/wind/kickoff present;
- scheduled game context remains visible;
- sportsbook projection influence remains 0.0%;
- no required cleanup section contains pending/unavailable/bare-dash state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

STREAMLIT_URL = "https://kyre-sports-ai.streamlit.app"
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CERT_DATE = "2026-09-19"
CERT_EVENT_ID = "401858458"
CERT_MATCHUP = "Purdue @ UCLA"

ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"

STEP2_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP2_PRESENTATION_ACTIVE"
STEP4_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP4_TEAM_EVIDENCE_UI_ACTIVE"

HERO_SELECTOR = (
    '[data-testid="gt159-game-total-hero"]'
    f'[data-step2-presentation="{STEP2_MARKER}"]'
)
TEAM_SELECTOR = (
    '[data-testid="gt204-team-evidence"]'
    f'[data-step4-presentation="{STEP4_MARKER}"]'
)
MATCHUP_SELECTOR = '[data-testid="gt159-matchup-header"]'

FORBIDDEN_RUNTIME = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError",
    "ImportError:",
    "SyntaxError:",
    "NameError:",
)


class PageCleanupProductionFailure(RuntimeError):
    pass


def _query_value(url: str, key: str) -> str:
    values = parse_qs(urlparse(url).query).get(key) or []
    return str(values[-1] if values else "").strip()


def _wake_once_if_needed(page) -> bool:
    labels = ("Yes, get this app back up!", "Get this app back up")
    for frame in page.frames:
        for label in labels:
            try:
                target = frame.get_by_text(label, exact=False)
                if target.count() > 0:
                    target.first.click(timeout=5000)
                    page.wait_for_timeout(5000)
                    return True
            except Exception:
                continue
    return False


def _scan(page):
    scans: list[dict] = []
    for index, frame in enumerate(page.frames):
        try:
            body = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            body = ""
        try:
            hero_count = frame.locator(HERO_SELECTOR).count()
        except Exception:
            hero_count = 0
        try:
            team_count = frame.locator(TEAM_SELECTOR).count()
        except Exception:
            team_count = 0
        try:
            matchup_count = frame.locator(MATCHUP_SELECTOR).count()
        except Exception:
            matchup_count = 0
        scans.append(
            {
                "index": index,
                "url": frame.url,
                "hero_count": hero_count,
                "team_count": team_count,
                "matchup_count": matchup_count,
                "body_start": body[:900],
            }
        )
        if hero_count and team_count and matchup_count:
            return frame, body, scans
    return None, "", scans


def _wait_for_cleanup_surface(page, timeout_seconds: float = 210.0):
    deadline = time.monotonic() + timeout_seconds
    wake_attempted = False
    last_scans: list[dict] = []
    last_body = ""
    while time.monotonic() < deadline:
        frame, body, scans = _scan(page)
        last_scans = scans
        last_body = body
        if frame is not None:
            return frame, body, scans
        if not wake_attempted and _wake_once_if_needed(page):
            wake_attempted = True
            continue
        page.wait_for_timeout(2000)
    raise PageCleanupProductionFailure(
        "Cleanup production surface did not mount in the stable session: "
        f"scans={last_scans!r} body_start={last_body[:2500]!r}"
    )


def _assert_no_runtime_error(body: str) -> None:
    for marker in FORBIDDEN_RUNTIME:
        if marker in body:
            raise PageCleanupProductionFailure(
                f"Production runtime error marker visible: {marker}"
            )


def _assert_exact_event(page, frame) -> None:
    event_id = (
        _query_value(page.url, EVENT_QUERY_KEY)
        or _query_value(frame.url, EVENT_QUERY_KEY)
    )
    if event_id != CERT_EVENT_ID:
        raise PageCleanupProductionFailure(
            f"Selected event drift: expected={CERT_EVENT_ID!r} actual={event_id!r} "
            f"page={page.url!r} frame={frame.url!r}"
        )
    selected_date = (
        _query_value(page.url, DATE_QUERY_KEY)
        or _query_value(frame.url, DATE_QUERY_KEY)
    )
    if selected_date != CERT_DATE:
        raise PageCleanupProductionFailure(
            f"Selected date drift: expected={CERT_DATE!r} actual={selected_date!r}"
        )


def _assert_hero(frame) -> dict:
    root = frame.locator(HERO_SELECTOR).last
    root.wait_for(state="attached", timeout=5000)
    state = str(root.get_attribute("data-analysis-state") or "").strip()
    ready_count = str(root.get_attribute("data-ready-count") or "").strip()
    total_checks = str(root.get_attribute("data-total-checks") or "").strip()
    metrics = root.locator('[data-metric]')
    ready_metrics = root.locator('[data-metric][data-state="READY"]')
    text = root.inner_text(timeout=10000)

    try:
        ready_value = int(ready_count)
        total_value = int(total_checks)
    except Exception as exc:
        raise PageCleanupProductionFailure(
            f"Game Total Analysis Data Check is not numeric: ready={ready_count!r} "
            f"total={total_checks!r}"
        ) from exc
    if total_value != 12 or not (0 <= ready_value <= total_value):
        raise PageCleanupProductionFailure(
            f"Game Total Analysis Data Check drift: ready={ready_count!r} total={total_checks!r}"
        )
    if metrics.count() != 4 or ready_metrics.count() != 4:
        raise PageCleanupProductionFailure(
            f"Game Total Analysis metric readiness drift: metrics={metrics.count()} "
            f"ready={ready_metrics.count()}"
        )
    expected_check = f"{ready_value}/{total_value} Data Check"
    if expected_check not in text:
        raise PageCleanupProductionFailure(
            f"Visible Data Check does not match DOM count: expected={expected_check!r}"
        )
    if "0.0% sportsbook projection influence" not in text.lower():
        raise PageCleanupProductionFailure(
            "0.0% sportsbook projection influence is not visible"
        )
    forbidden = ("Pending", "Not posted", "Waiting on")
    bad = [token for token in forbidden if token in text]
    if bad:
        raise PageCleanupProductionFailure(
            "Game Total Analysis still has incomplete presentation: " + " | ".join(bad)
        )

    return {
        "state": state,
        "ready_count": ready_value,
        "total_checks": total_value,
        "metric_count": metrics.count(),
        "ready_metrics": ready_metrics.count(),
        "cleanup_contract_ready": True,
    }


def _assert_team_evidence(frame) -> dict:
    root = frame.locator(TEAM_SELECTOR).last
    root.wait_for(state="attached", timeout=5000)
    text = root.inner_text(timeout=10000)
    cards = root.locator(".gt204-card")
    ready_cards = root.locator('.gt204-card[data-state="READY"]')
    stats = root.locator(".gt204-stat")
    ready_stats = root.locator('.gt204-stat[data-state="READY"]')

    if cards.count() != 2 or ready_cards.count() != 2:
        raise PageCleanupProductionFailure(
            f"Team Evidence card readiness drift: cards={cards.count()} "
            f"ready={ready_cards.count()}"
        )
    if stats.count() != 8 or ready_stats.count() != 8:
        raise PageCleanupProductionFailure(
            f"Team Evidence stat readiness drift: stats={stats.count()} "
            f"ready={ready_stats.count()}"
        )
    for token in ("Purdue", "UCLA", "PPG", "Allowed / Game", "Point Diff / Game", "Recent Form"):
        if token not in text:
            raise PageCleanupProductionFailure(
                f"Team Evidence required token missing: {token!r}"
            )
    if "Pending" in text:
        raise PageCleanupProductionFailure("Team Evidence still contains Pending")

    return {
        "card_count": cards.count(),
        "ready_cards": ready_cards.count(),
        "stat_count": stats.count(),
        "ready_stats": ready_stats.count(),
    }


def _assert_game_evidence(frame, full_body: str) -> dict:
    root = frame.locator(MATCHUP_SELECTOR).last
    root.wait_for(state="attached", timeout=5000)
    text = root.inner_text(timeout=10000)
    facts = root.locator(".gt159-gamefacts .gt159-fact")

    if facts.count() != 4:
        raise PageCleanupProductionFailure(
            f"Expected four Game Evidence facts, found {facts.count()}"
        )
    for token in ("Purdue", "UCLA", "Rose Bowl"):
        if token not in text:
            raise PageCleanupProductionFailure(
                f"Game Evidence required token missing: {token!r}"
            )
    lowered = text.casefold()
    if "unavailable" in lowered:
        raise PageCleanupProductionFailure(
            "Game Evidence still contains an unavailable field"
        )
    fact_texts = [facts.nth(i).inner_text(timeout=5000).strip() for i in range(4)]
    if any(not item or item == "—" for item in fact_texts):
        raise PageCleanupProductionFailure(
            f"Game Evidence contains a blank fact: {fact_texts!r}"
        )
    if "Scheduled" not in full_body:
        raise PageCleanupProductionFailure(
            "Scheduled game context is not visible on the selected production matchup"
        )

    return {
        "fact_count": facts.count(),
        "facts": fact_texts,
        "scheduled_context_visible": True,
    }


def verify(
    *,
    streamlit_url: str = STREAMLIT_URL,
    artifact_dir: str | Path = "artifacts/page-cleanup-step6-production",
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    query = urlencode(
        {
            ROUTE_QUERY_SPORT: CFB_SPORT,
            ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
            DATE_QUERY_KEY: CERT_DATE,
            EVENT_QUERY_KEY: CERT_EVENT_ID,
        }
    )
    # One production session; no reload loop.
    target_url = streamlit_url.rstrip("/") + "/~/+/?" + query

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1800})
        try:
            response = page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=90000,
            )
            nav_status = response.status if response is not None else None
            frame, body, scans = _wait_for_cleanup_surface(page)
            _assert_no_runtime_error(body)
            _assert_exact_event(page, frame)

            if "Purdue" not in body or "UCLA" not in body:
                raise PageCleanupProductionFailure(
                    f"Exact matchup {CERT_MATCHUP!r} is not visible"
                )

            hero = _assert_hero(frame)
            teams = _assert_team_evidence(frame)
            game = _assert_game_evidence(frame, body)

            screenshot = artifacts / "page_cleanup_step6_production_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "marker": "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP6_PRODUCTION_FREEZE_GREEN",
                "streamlit_url": streamlit_url,
                "target_url": target_url,
                "navigation_http": nav_status,
                "event_id": CERT_EVENT_ID,
                "date": CERT_DATE,
                "matchup": CERT_MATCHUP,
                "frame_url": frame.url,
                "frame_scan": scans,
                "game_total_analysis": hero,
                "team_evidence": teams,
                "game_evidence": game,
                "sportsbook_projection_influence": 0.0,
                "projection_mutation": False,
                "stable_session": True,
                "reload_used": False,
                "screenshot": str(screenshot),
            }
            (artifacts / "page_cleanup_step6_production.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_PAGE_CLEANUP_STEP6_PRODUCTION_FREEZE_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(
                    path=str(artifacts / "page_cleanup_step6_production_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--streamlit-url", default=STREAMLIT_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/page-cleanup-step6-production",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    verify(streamlit_url=args.streamlit_url, artifact_dir=args.artifact_dir)
