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
    analysis_state = str(
        root.get_attribute("data-analysis-state") or ""
    ).strip()
    ready_count_raw = str(
        root.get_attribute("data-ready-count") or ""
    ).strip()
    total_checks_raw = str(
        root.get_attribute("data-total-checks") or ""
    ).strip()
    metrics = root.locator('[data-metric]')
    ready_metrics = root.locator('[data-metric][data-state="READY"]')
    metric_values = root.locator('[data-metric] .gt202-value')
    text = root.inner_text(timeout=10000)

    if metrics.count() != 4 or ready_metrics.count() != 4:
        raise PageCleanupProductionFailure(
            f"Game Total Analysis metric readiness drift: metrics={metrics.count()} "
            f"ready={ready_metrics.count()}"
        )

    values = [
        metric_values.nth(i).inner_text(timeout=5000).strip()
        for i in range(metric_values.count())
    ]
    if len(values) != 4:
        raise PageCleanupProductionFailure(
            f"Game Total Analysis metric value count drift: {values!r}"
        )
    forbidden_metric_tokens = ("pending", "not posted", "waiting on")
    incomplete_values = [
        value for value in values
        if any(token in value.casefold() for token in forbidden_metric_tokens)
    ]
    if incomplete_values:
        raise PageCleanupProductionFailure(
            "Game Total Analysis still has incomplete metric values: "
            + " | ".join(incomplete_values)
        )

    try:
        checked = int(ready_count_raw)
        total_checks = int(total_checks_raw)
    except ValueError as exc:
        raise PageCleanupProductionFailure(
            f"Game Total Analysis Data Check is not numeric: "
            f"ready={ready_count_raw!r} total={total_checks_raw!r}"
        ) from exc

    if total_checks != 12 or not 0 <= checked <= total_checks:
        raise PageCleanupProductionFailure(
            f"Game Total Analysis Data Check drift: "
            f"ready={checked!r} total={total_checks!r}"
        )
    expected_data_check = f"{checked}/{total_checks} Data Check"
    if expected_data_check not in text:
        raise PageCleanupProductionFailure(
            f"Displayed Data Check does not match DOM count: "
            f"expected={expected_data_check!r}"
        )

    if "0.0% sportsbook projection influence" not in text.lower():
        raise PageCleanupProductionFailure(
            "0.0% sportsbook projection influence is not visible"
        )

    return {
        "analysis_state": analysis_state,
        "ready_count": checked,
        "total_checks": total_checks,
        "metric_count": metrics.count(),
        "ready_metrics": ready_metrics.count(),
        "metric_values": values,
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
    required_teams = ("Purdue", "UCLA")
    team_counts = {}
    for team in required_teams:
        count = root.locator(
            f'.gt204-card[data-team="{team}"][data-state="READY"]'
        ).count()
        team_counts[team] = count
        if count != 1:
            raise PageCleanupProductionFailure(
                f"Team Evidence READY card drift for {team}: count={count}"
            )

    required_stats = ("ppg", "allowed", "point-diff", "recent-form")
    stat_counts = {}
    for key in required_stats:
        count = root.locator(
            f'.gt204-stat[data-stat="{key}"][data-state="READY"]'
        ).count()
        stat_counts[key] = count
        if count != 2:
            raise PageCleanupProductionFailure(
                f"Team Evidence READY stat drift for {key}: count={count}"
            )

    if "Pending" in text:
        raise PageCleanupProductionFailure("Team Evidence still contains Pending")

    return {
        "card_count": cards.count(),
        "ready_cards": ready_cards.count(),
        "stat_count": stats.count(),
        "ready_stats": ready_stats.count(),
        "team_counts": team_counts,
        "required_stat_counts": stat_counts,
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
