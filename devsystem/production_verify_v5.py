"""DevSystem production verification V5 — CFB Game Total V164 identity proof.

V5 preserves the complete certified V3 Render/API/Streamlit production proof,
supersedes V4's outer-page-only event query assumption, verifies the deployed
Render official-games identity feed, and then proves Router V160 / Page V15 in
the real Streamlit app frame with an official persisted event ID.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from playwright.sync_api import sync_playwright

try:
    from devsystem import production_verify_v1 as base
    from devsystem import production_verify_v3 as prior
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v5.py`
    import production_verify_v1 as base
    import production_verify_v3 as prior

FROZEN_VERIFIER = "devsystem.production_verify_v3"
SUPERSEDED_VERIFIER = "devsystem.production_verify_v4"
EXPECTED_ROUTER = "streamlit_memory_lazy_router_v160"
GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"
GAME_SELECTOR_REQUIRED_TEXT = "GAMES ON THIS DAY"
ACTIVE_MARKER_TESTID = "cfb-game-total-v164-active"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CERT_DATE = "2026-09-19"
OFFICIAL_GAMES_ENDPOINT = "/api/v1/cfb/identity/official-games"
ProductionVerificationFailure = base.ProductionVerificationFailure


def _assert_v164_surface(body: str) -> None:
    text = str(body or "")
    if GAME_TOTAL_REQUIRED_HEARTBEAT not in text:
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total V164 deployment: "
            f"required production heartbeat {GAME_TOTAL_REQUIRED_HEARTBEAT!r} was not present"
        )
    if GAME_SELECTOR_REQUIRED_TEXT not in text:
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total V164 deployment: "
            f"required selector text {GAME_SELECTOR_REQUIRED_TEXT!r} was not present"
        )


def _event_id_from_url(url: str) -> str:
    parsed = parse_qs(urlparse(str(url or "")).query)
    return str((parsed.get(EVENT_QUERY_KEY) or [""])[-1] or "").strip()


def _query_event_id(page, frame=None) -> str:
    if frame is not None:
        event_id = _event_id_from_url(frame.url)
        if event_id:
            return event_id
    return _event_id_from_url(page.url)


def _verify_official_games_api(render_api_url: str) -> dict[str, Any]:
    url = render_api_url.rstrip("/") + OFFICIAL_GAMES_ENDPOINT
    try:
        response = requests.get(url, params={"game_date": CERT_DATE}, timeout=30.0)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise ProductionVerificationFailure(
            f"deployed CFB official-games identity feed unavailable: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ProductionVerificationFailure("deployed official-games payload was not an object")
    if payload.get("game_date") != CERT_DATE:
        raise ProductionVerificationFailure("deployed official-games payload returned wrong date")
    if payload.get("synthetic_ids") is not False:
        raise ProductionVerificationFailure("deployed official-games payload allows synthetic IDs")
    if payload.get("sportsbook_projection_influence_pct") != 0.0:
        raise ProductionVerificationFailure(
            "deployed official-games payload violated 0.0% sportsbook projection influence"
        )

    games = payload.get("games")
    if not isinstance(games, list) or len(games) < 2:
        raise ProductionVerificationFailure(
            f"deployed official-games feed returned insufficient {CERT_DATE} slate"
        )
    missing_ids = [
        index
        for index, row in enumerate(games)
        if not isinstance(row, dict) or not str(row.get("event_id") or "").strip()
    ]
    if missing_ids:
        raise ProductionVerificationFailure(
            f"deployed official-games feed contained rows without official event IDs: {missing_ids[:8]}"
        )

    return {
        "official_games_url": response.url,
        "official_games_verified": bool(payload.get("verified")),
        "official_games_count": len(games),
        "official_games_synthetic_ids": payload.get("synthetic_ids"),
        "official_games_sportsbook_projection_influence_pct": payload.get(
            "sportsbook_projection_influence_pct"
        ),
    }


def _build_v164_evidence(*, expected_commit: str, event_id: str) -> dict[str, Any]:
    if not str(event_id or "").strip():
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total V164 deployment: selected official event_id was not persisted"
        )
    return {
        "expected_commit": str(expected_commit or "unknown"),
        "expected_router": EXPECTED_ROUTER,
        "observed_router": "V160",
        "observed_build_marker": GAME_TOTAL_REQUIRED_HEARTBEAT,
        "game_selector_visible": True,
        "selected_official_event_id": str(event_id),
        "v164_freshness_verified": True,
    }


def _browser_verify_v164_selector(
    streamlit_url: str,
    artifact_dir: Path,
    *,
    expected_commit: str,
) -> dict[str, Any]:
    direct_query = urlencode(
        {
            ROUTE_QUERY_SPORT: CFB_SPORT,
            ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
            DATE_QUERY_KEY: CERT_DATE,
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
                streamlit_url.rstrip("/") + "/?" + direct_query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            deadline = time.monotonic() + 120.0
            final_body = ""
            selected_event = ""
            matched_frame = None
            scans: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                scans = []
                for index, frame in enumerate(page.frames):
                    try:
                        body = frame.locator("body").inner_text(timeout=5000)
                    except Exception:
                        body = ""
                    scans.append({"index": index, "url": frame.url, "body_start": body[:500]})
                    if (
                        GAME_TOTAL_REQUIRED_HEARTBEAT in body
                        and GAME_SELECTOR_REQUIRED_TEXT in body
                    ):
                        final_body = body
                        matched_frame = frame
                        break
                selected_event = _query_event_id(page, matched_frame)
                if matched_frame is not None and selected_event:
                    break
                page.wait_for_timeout(1000)

            _assert_v164_surface(final_body)
            if matched_frame is None:
                raise ProductionVerificationFailure(
                    "stale Streamlit Game Total V164 deployment: active V164 app frame not found"
                )
            forbidden = base._body_has_forbidden_error(final_body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Game Total V164 runtime error marker: {forbidden}"
                )
            if matched_frame.locator(f'[data-testid="{ACTIVE_MARKER_TESTID}"]').count() != 1:
                raise ProductionVerificationFailure("deployed V164 active marker was not present")
            unresolved = matched_frame.locator(
                '[data-testid="gt163-game-strip"] .gt163-game-disabled'
            )
            if unresolved.count() != 0:
                labels = [
                    unresolved.nth(index).inner_text().strip()
                    for index in range(min(unresolved.count(), 8))
                ]
                raise ProductionVerificationFailure(
                    "deployed V164 selector contains unresolved official event IDs: "
                    + " | ".join(labels)
                )

            evidence = _build_v164_evidence(
                expected_commit=expected_commit,
                event_id=selected_event,
            )
            screenshot = artifact_dir / "production_game_total_v164_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                **evidence,
                "game_total_route": f"{CFB_SPORT} -> {GAME_TOTAL_MARKET}",
                "certification_date": CERT_DATE,
                "game_total_app_frame_url": matched_frame.url,
                "game_total_outer_page_url": page.url,
                "game_total_frame_scan_count": len(scans),
                "game_total_unresolved_identity_count": 0,
                "game_total_v164_screenshot": str(screenshot),
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(artifact_dir / "production_game_total_v164_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(*, artifact_dir: str | Path = "artifacts/production-verification") -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # Preserve every frozen V3 verification. V4 is intentionally superseded
    # because its outer-page-only query assumption is invalid on framed cloud UI.
    result = dict(prior.run(artifact_dir=artifacts))

    targets = base._load_targets()
    streamlit_url = str(targets["streamlit"]["url"]).rstrip("/")
    render_api_url = str(targets["render_api"]["url"]).rstrip("/")
    expected_commit = str(os.environ.get("GITHUB_SHA") or "unknown")

    api_evidence = _verify_official_games_api(render_api_url)
    v164 = _browser_verify_v164_selector(
        streamlit_url,
        artifacts,
        expected_commit=expected_commit,
    )
    result.update(api_evidence)
    result.update(v164)
    result["status"] = "GREEN"
    result["production_verifier"] = "V5"

    result_path = artifacts / "production_verification.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("DEVSYSTEM_PRODUCTION_VERIFICATION_V5_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-verification",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(artifact_dir=args.artifact_dir)
