"""WNBA PRA Speed V3 Step 4 — production server-bundle-cache proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_nav_v2_step7_public_freeze import (
    VIEWPORT,
    _assert_no_overflow,
    _ensure_game_on_slate,
    _game_button,
    _player_final_surfaces_ready,
    _route_to_wnba_pra,
    _wait_page,
)
from devsystem.wnba_pra_speed_v3_step1_public_profile import (
    PROFILE_GAME_SETUP_TIMEOUT_SECONDS,
    PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS,
)
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST


API_BASE = "https://kyre-sports-api.onrender.com"
API_OPENAPI = API_BASE + "/openapi.json"
API_ROUTE_PATH = "/api/v1/wnba/players/{player_id}/pra-detail-cached"
STEP4_SELECTOR = '[data-wnba-pra-speed-v3-step4="server-bundle-cache"]'
STEP3_SELECTOR = '[data-wnba-pra-speed-v3-step3="detail-bundle"]'
STEP1_SELECTOR = '[data-wnba-pra-speed-v3-step1="profiler"]'

DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_TRUE_COLD_SECONDS = 2.5
MAX_CACHED_COLD_SECONDS = 1.5
MAX_WARM_SAME_SESSION_SECONDS = 0.75


def _wait_api_cache_route() -> float:
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
                print("WNBA_PRA_SPEED_V3_STEP4_API_CACHE_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP4_API_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return elapsed
            last = f"http={response.status_code};route_present={isinstance(paths, dict) and API_ROUTE_PATH in paths}"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        time.sleep(5.0)
    raise BrowserQAFailure(
        f"Kyre API did not expose Step-4 cache route within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _wait_step4_streamlit(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            marker = frame.locator(STEP4_SELECTOR)
            if marker.count() > 0:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_SPEED_V3_STEP4_STREAMLIT_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP4_STREAMLIT_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return frame, slate_seconds, elapsed
            last = "Step-4 cache marker absent"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)
    raise BrowserQAFailure(
        f"PickVault did not expose Step-4 marker within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _bool_attr(marker, name: str) -> bool:
    raw = str(marker.get_attribute(name) or "").strip().lower()
    if raw not in {"true", "false"}:
        raise BrowserQAFailure(f"Step-4 marker attribute {name} is not boolean: {raw!r}")
    return raw == "true"


def _int_attr(marker, name: str) -> int:
    raw = marker.get_attribute(name)
    try:
        return int(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Marker attribute {name} is not integer: {raw!r}") from exc


def _float_attr(marker, name: str) -> float:
    raw = marker.get_attribute(name)
    try:
        value = float(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Marker attribute {name} is not numeric: {raw!r}") from exc
    if value < 0:
        raise BrowserQAFailure(f"Marker attribute {name} is negative: {value}")
    return value


def _step4_marker(frame):
    marker = frame.locator(STEP4_SELECTOR)
    if marker.count() < 1:
        raise BrowserQAFailure("Step-4 cache marker disappeared on Player route.")
    return marker.first


def _step1_marker(frame):
    marker = frame.locator(STEP1_SELECTOR)
    if marker.count() < 1:
        raise BrowserQAFailure("Frozen Step-1 profiler marker missing on warm Player route.")
    return marker.first


def _cached_api_read(player_id: int) -> tuple[float, dict[str, Any]]:
    started = time.monotonic()
    response = requests.get(
        f"{API_BASE}/api/v1/wnba/players/{int(player_id)}/pra-detail-cached",
        params={"season": 2026},
        timeout=30.0,
    )
    elapsed = time.monotonic() - started
    if response.status_code != 200:
        raise BrowserQAFailure(f"Step-4 cached endpoint returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except Exception as exc:
        raise BrowserQAFailure(f"Step-4 cached endpoint returned invalid JSON: {type(exc).__name__}") from exc
    return elapsed, payload


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    api_wait_seconds = _wait_api_cache_route()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds, streamlit_wait_seconds = _wait_step4_streamlit(page)
            if frame.locator(STEP3_SELECTOR).count() < 1:
                raise BrowserQAFailure("Frozen Step-3 detail-bundle marker is missing.")

            frame = _ensure_game_on_slate(page, frame)
            game_started = time.monotonic()
            _game_button(frame).first.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)
            game_seconds = time.monotonic() - game_started

            player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if player_buttons.count() < 1:
                raise BrowserQAFailure("No Player PRA button available for Step-4 profiling.")
            player_button_name = player_buttons.first.inner_text().strip()

            first_started = time.monotonic()
            player_buttons.first.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)
            first_player_seconds = time.monotonic() - first_started
            _assert_no_overflow(frame, "player")

            final_ready, missing = _player_final_surfaces_ready(frame)
            if not final_ready:
                raise BrowserQAFailure(f"Frozen Player Intelligence surfaces missing: {missing}")

            marker = _step4_marker(frame)
            cache_used = _bool_attr(marker, "data-cache-used")
            network_reads = _int_attr(marker, "data-streamlit-network-reads")
            cached_bundle_read_ms = _float_attr(marker, "data-cached-bundle-read-ms")
            player_id = _int_attr(marker, "data-player-id")
            consumer_present = _bool_attr(marker, "data-consumer-present")
            history_present = _bool_attr(marker, "data-history-present")

            if not cache_used:
                raise BrowserQAFailure("Step-4 cached bundle loader was not used.")
            if network_reads != 1:
                raise BrowserQAFailure(f"Step-4 cold Player used {network_reads} hosted reads instead of 1.")
            if player_id <= 0:
                raise BrowserQAFailure("Step-4 marker did not expose a valid player id.")
            if not consumer_present or not history_present:
                raise BrowserQAFailure(
                    f"Step-4 Player data missing: consumer={consumer_present} history={history_present}"
                )
            if first_player_seconds > MAX_TRUE_COLD_SECONDS:
                raise BrowserQAFailure(
                    f"Step-4 first Player open exceeded true-cold target: "
                    f"{first_player_seconds:.3f}s > {MAX_TRUE_COLD_SECONDS:.3f}s"
                )

            cached_seconds, cached_payload = _cached_api_read(player_id)
            cache_meta = cached_payload.get("cache") if isinstance(cached_payload, dict) else None
            bundle = cached_payload.get("bundle") if isinstance(cached_payload, dict) else None
            if not isinstance(cache_meta, dict) or cache_meta.get("hit") is not True:
                raise BrowserQAFailure(f"Step-4 second server read was not a cache hit: {cache_meta!r}")
            if not isinstance(bundle, dict) or not isinstance(bundle.get("consumer"), dict) or not isinstance(bundle.get("history"), dict):
                raise BrowserQAFailure("Step-4 cached response did not preserve the finished Step-3 bundle.")
            if cached_seconds > MAX_CACHED_COLD_SECONDS:
                raise BrowserQAFailure(
                    f"Step-4 cached server read exceeded target: "
                    f"{cached_seconds:.3f}s > {MAX_CACHED_COLD_SECONDS:.3f}s"
                )

            back = frame.get_by_role("button", name="← Back to Game Center", exact=True)
            if back.count() < 1:
                raise BrowserQAFailure("Player back-to-game button missing before warm proof.")
            back.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)

            warm_button = frame.get_by_role("button", name=player_button_name, exact=True)
            if warm_button.count() < 1:
                # Stable game-card ordering fallback.
                warm_button = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$")).first

            warm_started = time.monotonic()
            warm_button.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)
            warm_seconds = time.monotonic() - warm_started
            _assert_no_overflow(frame, "player")

            warm_profile = _step1_marker(frame)
            warm_reads = _int_attr(warm_profile, "data-network-reads")
            consumer_session_hit = _bool_attr(warm_profile, "data-consumer-session-hit")
            history_session_hit = _bool_attr(warm_profile, "data-history-session-hit")

            if warm_seconds > MAX_WARM_SAME_SESSION_SECONDS:
                raise BrowserQAFailure(
                    f"Step-4 warm same-session reopen exceeded target: "
                    f"{warm_seconds:.3f}s > {MAX_WARM_SAME_SESSION_SECONDS:.3f}s"
                )
            if warm_reads != 0 or not consumer_session_hit or not history_session_hit:
                raise BrowserQAFailure(
                    "Step-4 warm reopen was not zero-read session reuse: "
                    f"reads={warm_reads} consumer_hit={consumer_session_hit} history_hit={history_session_hit}"
                )

            print("WNBA_PRA_SPEED_V3_STEP4_TRUE_COLD_GREEN")
            print(f"WNBA_PRA_SPEED_V3_STEP4_TRUE_COLD_SECONDS={first_player_seconds:.3f}")
            print("WNBA_PRA_SPEED_V3_STEP4_SERVER_CACHE_HIT_GREEN")
            print(f"WNBA_PRA_SPEED_V3_STEP4_CACHED_COLD_SECONDS={cached_seconds:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP4_CACHED_BUNDLE_READ_MS={cached_bundle_read_ms:.3f}")
            print("WNBA_PRA_SPEED_V3_STEP4_WARM_ZERO_READ_GREEN")
            print(f"WNBA_PRA_SPEED_V3_STEP4_WARM_SAME_SESSION_SECONDS={warm_seconds:.3f}")
            print("WNBA_PRA_SPEED_V3_STEP4_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "4/9",
                "status": "GREEN",
                "production_url": production_url,
                "api_deployment_wait_seconds": round(api_wait_seconds, 3),
                "streamlit_deployment_wait_seconds": round(streamlit_wait_seconds, 3),
                "slate_ready_seconds": round(slate_seconds, 3),
                "game_ready_seconds": round(game_seconds, 3),
                "true_cold_player_seconds": round(first_player_seconds, 3),
                "cached_cold_seconds": round(cached_seconds, 3),
                "warm_same_session_seconds": round(warm_seconds, 3),
                "cached_bundle_read_ms": round(cached_bundle_read_ms, 3),
                "player_id": player_id,
                "warm_network_reads": warm_reads,
                "consumer_session_hit": consumer_session_hit,
                "history_session_hit": history_session_hit,
                "frozen_step3_marker_green": True,
                "frozen_player_surface_green": True,
            }
            (artifacts / "wnba_pra_speed_v3_step4_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(artifacts / "wnba_pra_speed_v3_step4_profile.png"), full_page=True)
            print("WNBA_PRA_SPEED_V3_STEP4_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP4_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-pra-speed-v3-step4")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
