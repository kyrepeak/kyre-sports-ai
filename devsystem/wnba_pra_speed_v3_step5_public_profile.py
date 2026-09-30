"""WNBA PRA Speed V3 Step 5 — production cross-player consumer-reuse proof."""
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
API_ROUTE_PATH = "/api/v1/wnba/players/{player_id}/pra-history-fast"
STEP5_SELECTOR = '[data-wnba-pra-speed-v3-step5="cross-player-consumer-reuse"]'
STEP4_SELECTOR = '[data-wnba-pra-speed-v3-step4="server-bundle-cache"]'

DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_TRUE_COLD_SECONDS = 2.5
MAX_CROSS_PLAYER_SECONDS = 1.5
MAX_WARM_SAME_SESSION_SECONDS = 0.75
MARKER_STATE_WAIT_SECONDS = 10.0


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
                print("WNBA_PRA_SPEED_V3_STEP5_FAST_HISTORY_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP5_API_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return elapsed
            last = f"http={response.status_code};route_present={isinstance(paths, dict) and API_ROUTE_PATH in paths}"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        time.sleep(5.0)
    raise BrowserQAFailure(
        f"Kyre API did not expose Step-5 history route within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _wait_step5_streamlit(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            marker = frame.locator(STEP5_SELECTOR)
            if marker.count() > 0:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_SPEED_V3_STEP5_STREAMLIT_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP5_STREAMLIT_DEPLOYMENT_WAIT_SECONDS={elapsed:.3f}")
                return frame, slate_seconds, elapsed
            last = "Step-5 marker absent"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)
    raise BrowserQAFailure(
        f"PickVault did not expose Step-5 marker within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _bool_attr(marker, name: str) -> bool:
    raw = str(marker.get_attribute(name) or "").strip().lower()
    if raw not in {"true", "false"}:
        raise BrowserQAFailure(f"Step-5 marker attribute {name} is not boolean: {raw!r}")
    return raw == "true"


def _int_attr(marker, name: str) -> int:
    raw = marker.get_attribute(name)
    try:
        return int(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Step-5 marker attribute {name} is not integer: {raw!r}") from exc


def _marker(frame):
    marker = frame.locator(STEP5_SELECTOR)
    if marker.count() < 1:
        raise BrowserQAFailure("Step-5 marker disappeared.")
    return marker.first


def _wait_marker_state(
    frame,
    *,
    consumer_hit: bool,
    history_hit: bool,
    consumer_reads: int,
    history_reads: int,
    direct_reads: int,
    fast_history: bool,
    cold_pair: bool,
    suppressed: bool,
    timeout_seconds: float = MARKER_STATE_WAIT_SECONDS,
):
    """Wait for the marker produced by the current Player render, not stale DOM state."""
    selector = (
        STEP5_SELECTOR
        + f'[data-consumer-session-hit="{str(bool(consumer_hit)).lower()}"]'
        + f'[data-history-session-hit="{str(bool(history_hit)).lower()}"]'
        + f'[data-consumer-network-reads="{int(consumer_reads)}"]'
        + f'[data-history-network-reads="{int(history_reads)}"]'
        + f'[data-direct-network-reads="{int(direct_reads)}"]'
        + f'[data-fast-history-used="{str(bool(fast_history)).lower()}"]'
        + f'[data-cold-pair-loader-used="{str(bool(cold_pair)).lower()}"]'
        + f'[data-duplicate-consumer-read-suppressed="{str(bool(suppressed)).lower()}"]'
        + '[data-consumer-present="true"]'
        + '[data-history-present="true"]'
    )
    marker = frame.locator(selector).first
    try:
        marker.wait_for(state="attached", timeout=int(float(timeout_seconds) * 1000))
        return marker
    except Exception as exc:
        current = _marker(frame)
        snapshot = {
            "player_id": current.get_attribute("data-player-id"),
            "consumer_hit": current.get_attribute("data-consumer-session-hit"),
            "history_hit": current.get_attribute("data-history-session-hit"),
            "consumer_reads": current.get_attribute("data-consumer-network-reads"),
            "history_reads": current.get_attribute("data-history-network-reads"),
            "direct_reads": current.get_attribute("data-direct-network-reads"),
            "fast_history": current.get_attribute("data-fast-history-used"),
            "cold_pair": current.get_attribute("data-cold-pair-loader-used"),
            "suppressed": current.get_attribute("data-duplicate-consumer-read-suppressed"),
        }
        raise BrowserQAFailure(
            "Step-5 marker did not synchronize to the expected Player render "
            f"within {timeout_seconds:.1f}s; last={snapshot}"
        ) from exc


def _assert_player_ready(frame):
    _assert_no_overflow(frame, "player")
    final_ready, missing = _player_final_surfaces_ready(frame)
    if not final_ready:
        raise BrowserQAFailure(f"Frozen Player Intelligence surfaces missing: {missing}")


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    api_wait_seconds = _wait_api_route()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds, streamlit_wait_seconds = _wait_step5_streamlit(page)
            if frame.locator(STEP4_SELECTOR).count() < 1:
                raise BrowserQAFailure("Frozen Step-4 cache marker is missing.")

            frame = _ensure_game_on_slate(page, frame)
            _game_button(frame).first.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)

            buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if buttons.count() < 2:
                raise BrowserQAFailure("Step-5 production proof requires at least two Player PRA buttons.")
            first_name = buttons.nth(0).inner_text().strip()
            second_name = buttons.nth(1).inner_text().strip()

            first_started = time.monotonic()
            buttons.nth(0).click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)
            first_seconds = time.monotonic() - first_started
            _assert_player_ready(frame)
            if first_seconds > MAX_TRUE_COLD_SECONDS:
                raise BrowserQAFailure(
                    f"Step-5 frozen true-cold path regressed: {first_seconds:.3f}s > {MAX_TRUE_COLD_SECONDS:.3f}s"
                )

            back = frame.get_by_role("button", name="← Back to Game Center", exact=True)
            back.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)

            second = frame.get_by_role("button", name=second_name, exact=True)
            if second.count() < 1:
                second = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$")).nth(1)

            cross_started = time.monotonic()
            second.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)
            cross_seconds = time.monotonic() - cross_started
            _assert_player_ready(frame)

            marker = _wait_marker_state(
                frame,
                consumer_hit=True,
                history_hit=False,
                consumer_reads=0,
                history_reads=1,
                direct_reads=1,
                fast_history=True,
                cold_pair=False,
                suppressed=True,
            )
            player_id = _int_attr(marker, "data-player-id")
            consumer_hit = _bool_attr(marker, "data-consumer-session-hit")
            history_hit = _bool_attr(marker, "data-history-session-hit")
            consumer_reads = _int_attr(marker, "data-consumer-network-reads")
            history_reads = _int_attr(marker, "data-history-network-reads")
            direct_reads = _int_attr(marker, "data-direct-network-reads")
            fast_history = _bool_attr(marker, "data-fast-history-used")
            cold_pair = _bool_attr(marker, "data-cold-pair-loader-used")
            suppressed = _bool_attr(marker, "data-duplicate-consumer-read-suppressed")
            consumer_present = _bool_attr(marker, "data-consumer-present")
            history_present = _bool_attr(marker, "data-history-present")

            if cross_seconds > MAX_CROSS_PLAYER_SECONDS:
                raise BrowserQAFailure(
                    f"Step-5 cross-player open exceeded target: {cross_seconds:.3f}s > {MAX_CROSS_PLAYER_SECONDS:.3f}s"
                )
            if not consumer_hit or history_hit:
                raise BrowserQAFailure(
                    f"Step-5 did not exercise consumer-hit/new-history path: consumer_hit={consumer_hit} history_hit={history_hit}"
                )
            if consumer_reads != 0 or history_reads != 1 or direct_reads != 1:
                raise BrowserQAFailure(
                    f"Step-5 cross-player reads invalid: consumer={consumer_reads} history={history_reads} total={direct_reads}"
                )
            if not fast_history or cold_pair or not suppressed:
                raise BrowserQAFailure(
                    f"Step-5 route ownership invalid: fast_history={fast_history} cold_pair={cold_pair} suppressed={suppressed}"
                )
            if not consumer_present or not history_present or player_id <= 0:
                raise BrowserQAFailure("Step-5 cross-player payload is incomplete.")

            back = frame.get_by_role("button", name="← Back to Game Center", exact=True)
            back.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)

            warm = frame.get_by_role("button", name=second_name, exact=True)
            if warm.count() < 1:
                warm = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$")).nth(1)

            warm_started = time.monotonic()
            warm.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)
            warm_seconds = time.monotonic() - warm_started
            _assert_player_ready(frame)

            warm_marker = _wait_marker_state(
                frame,
                consumer_hit=True,
                history_hit=True,
                consumer_reads=0,
                history_reads=0,
                direct_reads=0,
                fast_history=False,
                cold_pair=False,
                suppressed=False,
            )
            warm_consumer_hit = _bool_attr(warm_marker, "data-consumer-session-hit")
            warm_history_hit = _bool_attr(warm_marker, "data-history-session-hit")
            warm_reads = _int_attr(warm_marker, "data-direct-network-reads")

            if warm_seconds > MAX_WARM_SAME_SESSION_SECONDS:
                raise BrowserQAFailure(
                    f"Step-5 warm reopen exceeded target: {warm_seconds:.3f}s > {MAX_WARM_SAME_SESSION_SECONDS:.3f}s"
                )
            if warm_reads != 0 or not warm_consumer_hit or not warm_history_hit:
                raise BrowserQAFailure(
                    f"Step-5 warm reopen was not zero-read reuse: reads={warm_reads} consumer_hit={warm_consumer_hit} history_hit={warm_history_hit}"
                )

            print("WNBA_PRA_SPEED_V3_STEP5_CONSUMER_REUSE_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP5_ZERO_DUPLICATE_CONSUMER_READ_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP5_FAST_HISTORY_GREEN")
            print(f"WNBA_PRA_SPEED_V3_STEP5_TRUE_COLD_SECONDS={first_seconds:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP5_CROSS_PLAYER_SECONDS={cross_seconds:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP5_WARM_SAME_SESSION_SECONDS={warm_seconds:.3f}")
            print("WNBA_PRA_SPEED_V3_STEP5_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "5/9",
                "status": "GREEN",
                "production_url": production_url,
                "api_deployment_wait_seconds": round(api_wait_seconds, 3),
                "streamlit_deployment_wait_seconds": round(streamlit_wait_seconds, 3),
                "slate_ready_seconds": round(slate_seconds, 3),
                "true_cold_player_seconds": round(first_seconds, 3),
                "cross_player_seconds": round(cross_seconds, 3),
                "warm_same_session_seconds": round(warm_seconds, 3),
                "second_player_id": player_id,
                "consumer_network_reads": consumer_reads,
                "history_network_reads": history_reads,
                "warm_network_reads": warm_reads,
                "frozen_step4_marker_green": True,
            }
            (artifacts / "wnba_pra_speed_v3_step5_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(
                path=str(artifacts / "wnba_pra_speed_v3_step5_profile.png"),
                full_page=True,
            )
            print("WNBA_PRA_SPEED_V3_STEP5_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP5_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-pra-speed-v3-step5")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
