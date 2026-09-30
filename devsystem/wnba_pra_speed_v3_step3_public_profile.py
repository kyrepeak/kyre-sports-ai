"""WNBA PRA Speed V3 Step 3 — production single-request detail-bundle proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _find_app_frame
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
API_ROUTE_PATH = "/api/v1/wnba/players/{player_id}/pra-detail"
STEP3_SELECTOR = '[data-wnba-pra-speed-v3-step3="detail-bundle"]'
STEP2_SELECTOR = '[data-wnba-pra-speed-v3-step2="pooled-http"]'
DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_PLAYER_READY_SECONDS = 7.5


def _wait_api_bundle() -> float:
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
                print("WNBA_PRA_SPEED_V3_STEP3_API_BUNDLE_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP3_API_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return elapsed
            last = f"http={response.status_code};route_present={isinstance(paths, dict) and API_ROUTE_PATH in paths}"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        time.sleep(5.0)
    raise BrowserQAFailure(
        f"Kyre API did not expose Step-3 PRA detail route within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _wait_step3_streamlit(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            marker = frame.locator(STEP3_SELECTOR)
            if marker.count() > 0:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_SPEED_V3_STEP3_STREAMLIT_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP3_STREAMLIT_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return frame, slate_seconds, elapsed
            last = "Step-3 marker absent"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)
    raise BrowserQAFailure(
        f"PickVault did not expose Step-3 marker within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _bool_attr(marker, name: str) -> bool:
    raw = str(marker.get_attribute(name) or "").strip().lower()
    if raw not in {"true", "false"}:
        raise BrowserQAFailure(f"Step-3 marker attribute {name} is not boolean: {raw!r}")
    return raw == "true"


def _int_attr(marker, name: str) -> int:
    raw = marker.get_attribute(name)
    try:
        return int(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Step-3 marker attribute {name} is not integer: {raw!r}") from exc


def _float_attr(marker, name: str) -> float:
    raw = marker.get_attribute(name)
    try:
        value = float(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Step-3 marker attribute {name} is not numeric: {raw!r}") from exc
    if value < 0:
        raise BrowserQAFailure(f"Step-3 marker attribute {name} is negative: {value}")
    return value


def _step3_marker(frame):
    marker = frame.locator(STEP3_SELECTOR)
    if marker.count() < 1:
        raise BrowserQAFailure("Step-3 detail-bundle marker disappeared on Player route.")
    return marker.first


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    api_wait_seconds = _wait_api_bundle()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds, streamlit_wait_seconds = _wait_step3_streamlit(page)
            if frame.locator(STEP2_SELECTOR).count() < 1:
                raise BrowserQAFailure("Frozen Step-2 pooled transport marker is missing.")

            frame = _ensure_game_on_slate(page, frame)
            game_started = time.monotonic()
            _game_button(frame).first.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)
            game_seconds = time.monotonic() - game_started

            player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if player_buttons.count() < 1:
                raise BrowserQAFailure("No Player PRA button available for Step-3 profiling.")

            player_started = time.monotonic()
            player_buttons.first.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)
            player_seconds = time.monotonic() - player_started
            _assert_no_overflow(frame, "player")

            final_ready, missing = _player_final_surfaces_ready(frame)
            if not final_ready:
                raise BrowserQAFailure(f"Frozen Player Intelligence surfaces missing: {missing}")

            marker = _step3_marker(frame)
            bundle_used = _bool_attr(marker, "data-bundle-used")
            network_reads = _int_attr(marker, "data-streamlit-network-reads")
            bundle_read_ms = _float_attr(marker, "data-bundle-read-ms")
            consumer_present = _bool_attr(marker, "data-consumer-present")
            history_present = _bool_attr(marker, "data-history-present")
            consumer_error = str(marker.get_attribute("data-consumer-error") or "")
            history_error = str(marker.get_attribute("data-history-error") or "")

            if not bundle_used:
                raise BrowserQAFailure("Step-3 cold-pair bundle was not used in the fresh session.")
            if network_reads != 1:
                raise BrowserQAFailure(f"Step-3 cold pair used {network_reads} Streamlit API reads instead of 1.")
            if not consumer_present or not history_present:
                raise BrowserQAFailure(
                    f"Step-3 bundle data missing: consumer={consumer_present} history={history_present} "
                    f"consumer_error={consumer_error!r} history_error={history_error!r}"
                )
            if consumer_error or history_error:
                raise BrowserQAFailure(
                    f"Step-3 bundle component error: consumer={consumer_error!r} history={history_error!r}"
                )
            if player_seconds > MAX_PLAYER_READY_SECONDS:
                raise BrowserQAFailure(
                    f"Step-3 public PRA materially regressed: {player_seconds:.3f}s > {MAX_PLAYER_READY_SECONDS:.3f}s"
                )

            print("WNBA_PRA_SPEED_V3_STEP3_ONE_READ_GREEN")
            print(f"WNBA_PRA_SPEED_V3_STEP3_PUBLIC_PLAYER_READY_SECONDS={player_seconds:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP3_BUNDLE_READ_MS={bundle_read_ms:.3f}")
            print("WNBA_PRA_SPEED_V3_STEP3_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "3/9",
                "status": "GREEN",
                "production_url": production_url,
                "api_deployment_wait_seconds": round(api_wait_seconds, 3),
                "streamlit_deployment_wait_seconds": round(streamlit_wait_seconds, 3),
                "slate_ready_seconds": round(slate_seconds, 3),
                "game_ready_seconds": round(game_seconds, 3),
                "player_ready_seconds": round(player_seconds, 3),
                "bundle_read_ms": round(bundle_read_ms, 3),
                "streamlit_network_reads": network_reads,
                "consumer_present": consumer_present,
                "history_present": history_present,
                "frozen_step2_marker_green": True,
                "frozen_player_surface_green": True,
            }
            (artifacts / "wnba_pra_speed_v3_step3_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(artifacts / "wnba_pra_speed_v3_step3_profile.png"), full_page=True)
            print("WNBA_PRA_SPEED_V3_STEP3_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP3_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-pra-speed-v3-step3")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
