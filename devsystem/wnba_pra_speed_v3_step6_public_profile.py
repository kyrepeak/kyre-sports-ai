"""WNBA PRA Speed V3 Step 6 — production smarter-history-cache proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_nav_v2_step7_public_freeze import VIEWPORT, _route_to_wnba_pra
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_pra_speed_v3_step5_public_profile as step5_profile

API_BASE = "https://kyre-sports-api.onrender.com"
API_OPENAPI = API_BASE + "/openapi.json"
API_ROUTE_PATH = "/api/v1/wnba/players/{player_id}/pra-history-cached"
STEP6_SELECTOR = '[data-wnba-pra-speed-v3-step6="history-cache"]'

DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_CACHED_HISTORY_SECONDS = 1.5
EXPECTED_ACTIVE_TTL_SECONDS = 600


def _wait_api_route() -> float:
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            response = requests.get(API_OPENAPI, timeout=30.0)
            payload = response.json() if response.status_code == 200 else {}
            paths = payload.get("paths") if isinstance(payload, dict) else None
            if isinstance(paths, dict) and API_ROUTE_PATH in paths:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_SPEED_V3_STEP6_HISTORY_CACHE_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP6_API_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return elapsed
            last = (
                f"http={response.status_code};"
                f"route_present={isinstance(paths, dict) and API_ROUTE_PATH in paths}"
            )
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        time.sleep(5.0)
    raise BrowserQAFailure(
        "Kyre API did not expose Step-6 history-cache route within "
        f"{DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _wait_step6_streamlit(production_url: str) -> float:
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(
                production_url,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            while time.monotonic() < deadline:
                try:
                    frame, _ = _route_to_wnba_pra(page)
                    marker = frame.locator(STEP6_SELECTOR)
                    if marker.count() > 0:
                        elapsed = time.monotonic() - started
                        print("WNBA_PRA_SPEED_V3_STEP6_STREAMLIT_DEPLOYED_GREEN")
                        print(
                            "WNBA_PRA_SPEED_V3_STEP6_STREAMLIT_DEPLOYMENT_WAIT_SECONDS="
                            f"{elapsed:.3f}"
                        )
                        return elapsed
                    last = "Step-6 marker absent"
                except Exception as exc:
                    last = f"{type(exc).__name__}:{str(exc)[:300]}"
                page.wait_for_timeout(5000)
                page.reload(wait_until="domcontentloaded", timeout=120000)
        finally:
            context.close()
            browser.close()

    raise BrowserQAFailure(
        f"PickVault did not expose Step-6 marker within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _cached_history_read(player_id: int) -> tuple[float, dict[str, Any]]:
    started = time.monotonic()
    response = requests.get(
        f"{API_BASE}/api/v1/wnba/players/{int(player_id)}/pra-history-cached",
        params={"season": 2026},
        timeout=30.0,
    )
    elapsed = time.monotonic() - started
    if response.status_code != 200:
        raise BrowserQAFailure(
            f"Step-6 cached-history endpoint returned HTTP {response.status_code}."
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise BrowserQAFailure(
            f"Step-6 cached-history endpoint returned invalid JSON: {type(exc).__name__}"
        ) from exc
    if not isinstance(payload, dict):
        raise BrowserQAFailure("Step-6 cached-history endpoint returned a non-object.")
    return elapsed, payload


def _assert_cache_payload(
    payload: dict[str, Any],
    *,
    player_id: int,
    require_hit: bool,
) -> dict[str, Any]:
    if payload.get("data_type") != "wnba_pra_speed_v3_step6_history_cache":
        raise BrowserQAFailure("Step-6 cached-history data_type drifted.")
    if payload.get("schema_version") != "wnba_pra_speed_v3_step6_history_cache_v1":
        raise BrowserQAFailure("Step-6 cached-history schema_version drifted.")
    if int(payload.get("player_id") or 0) != int(player_id):
        raise BrowserQAFailure("Step-6 cached-history player identity drifted.")
    if int(payload.get("season") or 0) != 2026:
        raise BrowserQAFailure("Step-6 cached-history season drifted.")

    history = payload.get("history")
    if not isinstance(history, dict):
        raise BrowserQAFailure("Step-6 cached-history payload is missing history.")
    if int(history.get("player_id") or 0) != int(player_id):
        raise BrowserQAFailure("Step-6 cached history contains the wrong player.")
    if int(history.get("season") or 0) != 2026:
        raise BrowserQAFailure("Step-6 cached history contains the wrong season.")

    cache = payload.get("cache")
    if not isinstance(cache, dict):
        raise BrowserQAFailure("Step-6 cache metadata is missing.")
    if require_hit and cache.get("hit") is not True:
        raise BrowserQAFailure(f"Step-6 second history read was not a cache hit: {cache!r}")
    if int(cache.get("ttl_seconds") or 0) != EXPECTED_ACTIVE_TTL_SECONDS:
        raise BrowserQAFailure(
            "Step-6 active-season TTL drifted: "
            f"{cache.get('ttl_seconds')!r} != {EXPECTED_ACTIVE_TTL_SECONDS}"
        )

    semantics = payload.get("semantics")
    if not isinstance(semantics, dict):
        raise BrowserQAFailure("Step-6 semantics are missing.")
    if semantics.get("step6_longer_history_cache") is not True:
        raise BrowserQAFailure("Step-6 longer-cache semantic marker is false.")
    if semantics.get("consumer_snapshot_read") is not False:
        raise BrowserQAFailure("Step-6 history cache unexpectedly read the consumer snapshot.")
    return cache


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    api_wait_seconds = _wait_api_route()
    streamlit_wait_seconds = _wait_step6_streamlit(production_url)

    step5_result = step5_profile.run(
        production_url=production_url,
        artifact_dir=artifacts / "frozen-step5",
    )
    if step5_result.get("status") != "GREEN":
        raise BrowserQAFailure("Frozen Step-5 production profile did not remain GREEN.")

    player_id = int(step5_result.get("second_player_id") or 0)
    if player_id <= 0:
        raise BrowserQAFailure("Frozen Step-5 profile did not return a valid Player-B id.")

    first_seconds, first_payload = _cached_history_read(player_id)
    _assert_cache_payload(
        first_payload,
        player_id=player_id,
        require_hit=False,
    )

    second_seconds, second_payload = _cached_history_read(player_id)
    second_cache = _assert_cache_payload(
        second_payload,
        player_id=player_id,
        require_hit=True,
    )

    if second_seconds > MAX_CACHED_HISTORY_SECONDS:
        raise BrowserQAFailure(
            "Step-6 cached history read exceeded target: "
            f"{second_seconds:.3f}s > {MAX_CACHED_HISTORY_SECONDS:.3f}s"
        )

    print("WNBA_PRA_SPEED_V3_STEP6_FROZEN_STEP5_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP6_HISTORY_CACHE_HIT_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP6_ACTIVE_TTL_GREEN")
    print(f"WNBA_PRA_SPEED_V3_STEP6_FIRST_API_SECONDS={first_seconds:.3f}")
    print(f"WNBA_PRA_SPEED_V3_STEP6_CACHED_API_SECONDS={second_seconds:.3f}")
    print(
        "WNBA_PRA_SPEED_V3_STEP6_CACHE_AGE_MS="
        f"{float(second_cache.get('age_ms') or 0.0):.3f}"
    )
    print("WNBA_PRA_SPEED_V3_STEP6_PROFILE_GREEN")

    result = {
        "project": "WNBA PRA Speed V3",
        "step": "6/9",
        "status": "GREEN",
        "production_url": production_url,
        "api_deployment_wait_seconds": round(api_wait_seconds, 3),
        "streamlit_deployment_wait_seconds": round(streamlit_wait_seconds, 3),
        "player_id": player_id,
        "first_api_seconds": round(first_seconds, 3),
        "cached_api_seconds": round(second_seconds, 3),
        "cache_hit": True,
        "active_ttl_seconds": int(second_cache.get("ttl_seconds") or 0),
        "cache_age_ms": round(float(second_cache.get("age_ms") or 0.0), 3),
        "frozen_step5_true_cold_seconds": step5_result.get("true_cold_player_seconds"),
        "frozen_step5_cross_player_seconds": step5_result.get("cross_player_seconds"),
        "frozen_step5_warm_seconds": step5_result.get("warm_same_session_seconds"),
    }
    (artifacts / "wnba_pra_speed_v3_step6_profile.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("WNBA_PRA_SPEED_V3_STEP6_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP6_FROZEN")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-speed-v3-step6",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
