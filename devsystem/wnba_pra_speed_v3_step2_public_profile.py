"""WNBA PRA Speed V3 Step 2 — production pooled-HTTP proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from typing import Any

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
    PUBLIC_HOST,
    PROFILE_GAME_SETUP_TIMEOUT_SECONDS,
    PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS,
    _bool_attr,
    _dominant_phase,
    _float_attr,
    _wait_profile_marker,
)

STEP2_SELECTOR = '[data-wnba-pra-speed-v3-step2="pooled-http"]'
DEPLOYMENT_WAIT_SECONDS = 600.0
STEP1_HISTORY_BASELINE_MS = 5135.015
STEP1_PLAYER_READY_BASELINE_SECONDS = 5.629
MAX_HISTORY_READ_MS = 5500.0
MAX_PLAYER_READY_SECONDS = 7.5


def _step2_profile(marker) -> dict[str, Any]:
    """Parse frozen Step-1 timing markers without Step-1's non-nested loader assertion."""
    values = {
        "total_render_ms": _float_attr(marker, "data-total-render-ms"),
        "player_loader_ms": _float_attr(marker, "data-player-loader-ms"),
        "consumer_read_ms": _float_attr(marker, "data-consumer-read-ms"),
        "history_read_ms": _float_attr(marker, "data-history-read-ms"),
        "decision_card_ms": _float_attr(marker, "data-decision-card-ms"),
        "history_summary_ms": _float_attr(marker, "data-history-summary-ms"),
        "post_loader_render_ms": _float_attr(marker, "data-post-loader-render-ms"),
    }
    network_raw = marker.get_attribute("data-network-reads")
    try:
        network_reads = int(network_raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Profiler network read count is invalid: {network_raw!r}") from exc
    if network_reads < 0 or network_reads > 2:
        raise BrowserQAFailure(f"Profiler network read count escaped frozen contract: {network_reads}")

    values.update({
        "network_reads": network_reads,
        "consumer_session_hit": _bool_attr(marker, "data-consumer-session-hit"),
        "history_session_hit": _bool_attr(marker, "data-history-session-hit"),
        "cold_pair_loader_used": _bool_attr(marker, "data-cold-pair-loader"),
    })
    if values["total_render_ms"] <= 0:
        raise BrowserQAFailure("Profiler total render timing is empty.")
    return values


def _wait_step2_deployment(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            marker = frame.locator(STEP2_SELECTOR)
            if marker.count() > 0:
                if marker.first.get_attribute("data-pool-connections") != "8":
                    raise BrowserQAFailure("Step-2 pool-connections marker drifted.")
                if marker.first.get_attribute("data-pool-maxsize") != "16":
                    raise BrowserQAFailure("Step-2 pool-maxsize marker drifted.")
                if marker.first.get_attribute("data-hidden-retries") != "0":
                    raise BrowserQAFailure("Step-2 hidden-retry marker drifted.")
                print("WNBA_PRA_SPEED_V3_STEP2_POOL_DEPLOYED_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP2_DEPLOYMENT_WAIT_SECONDS={time.monotonic() - started:.3f}")
                return frame, slate_seconds
            last = "Step-2 marker absent"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:400]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)
    raise BrowserQAFailure(
        f"PickVault did not expose Step-2 pooled transport within {DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds = _wait_step2_deployment(page)
            frame = _ensure_game_on_slate(page, frame)

            game_started = time.monotonic()
            _game_button(frame).first.click()
            frame, _ = _wait_page(
                page,
                "game",
                timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS,
            )
            game_seconds = time.monotonic() - game_started

            player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if player_buttons.count() < 1:
                raise BrowserQAFailure("No Player PRA button available for Step-2 profiling.")

            player_started = time.monotonic()
            player_buttons.first.click()
            frame, _ = _wait_page(
                page,
                "player",
                timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS,
            )
            player_seconds = time.monotonic() - player_started
            _assert_no_overflow(frame, "player")

            if frame.locator(STEP2_SELECTOR).count() < 1:
                raise BrowserQAFailure("Step-2 pooled transport marker disappeared on Player route.")

            final_ready, missing = _player_final_surfaces_ready(frame)
            if not final_ready:
                raise BrowserQAFailure(f"Frozen Player Intelligence surfaces missing: {missing}")

            frame, marker = _wait_profile_marker(page)
            profile = _step2_profile(marker)
            dominant, dominant_ms = _dominant_phase(profile)

            history_ms = float(profile["history_read_ms"])
            history_delta_ms = history_ms - STEP1_HISTORY_BASELINE_MS
            player_delta_seconds = player_seconds - STEP1_PLAYER_READY_BASELINE_SECONDS

            if history_ms > MAX_HISTORY_READ_MS:
                raise BrowserQAFailure(
                    f"Step-2 history transport materially regressed: {history_ms:.3f}ms > {MAX_HISTORY_READ_MS:.3f}ms"
                )
            if player_seconds > MAX_PLAYER_READY_SECONDS:
                raise BrowserQAFailure(
                    f"Step-2 public PRA materially regressed: {player_seconds:.3f}s > {MAX_PLAYER_READY_SECONDS:.3f}s"
                )

            print(f"WNBA_PRA_SPEED_V3_STEP2_PUBLIC_PLAYER_READY_SECONDS={player_seconds:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP2_HISTORY_READ_MS={history_ms:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP2_HISTORY_DELTA_MS={history_delta_ms:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP2_PLAYER_READY_DELTA_SECONDS={player_delta_seconds:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP2_DOMINANT_PHASE={dominant}")
            print(f"WNBA_PRA_SPEED_V3_STEP2_DOMINANT_PHASE_MS={dominant_ms:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP2_NETWORK_READS={profile['network_reads']}")
            print("WNBA_PRA_SPEED_V3_STEP2_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "2/9",
                "status": "GREEN",
                "production_url": production_url,
                "slate_ready_seconds": round(slate_seconds, 3),
                "game_ready_seconds": round(game_seconds, 3),
                "player_ready_seconds": round(player_seconds, 3),
                "step1_player_ready_baseline_seconds": STEP1_PLAYER_READY_BASELINE_SECONDS,
                "player_ready_delta_seconds": round(player_delta_seconds, 3),
                "step1_history_baseline_ms": STEP1_HISTORY_BASELINE_MS,
                "history_read_ms": round(history_ms, 3),
                "history_delta_ms": round(history_delta_ms, 3),
                "profile": profile,
                "dominant_phase": dominant,
                "dominant_phase_ms": round(dominant_ms, 3),
                "pool_connections": 8,
                "pool_maxsize": 16,
                "adapter_hidden_retries": 0,
                "frozen_player_surface_green": True,
            }
            (artifacts / "wnba_pra_speed_v3_step2_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(artifacts / "wnba_pra_speed_v3_step2_profile.png"), full_page=True)
            print("WNBA_PRA_SPEED_V3_STEP2_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP2_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-pra-speed-v3-step2")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
