"""WNBA PRA Speed V3 Step 1 — public profiler proof."""
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
    BACK_READY_BUDGET_SECONDS,
    GAME_READY_BUDGET_SECONDS,
    PLAYER_READY_BUDGET_SECONDS,
    PUBLIC_HOST,
    VIEWPORT,
    _assert_no_overflow,
    _ensure_game_on_slate,
    _game_button,
    _player_final_surfaces_ready,
    _route_to_wnba_pra,
    _wait_page,
)

PROFILE_SELECTOR = '[data-wnba-pra-speed-v3-step1="profiler"]'
PROFILE_DEPLOYMENT_SELECTOR = '[data-wnba-pra-speed-v3-step1-deployed="true"]'
DEPLOYMENT_READY_BUDGET_SECONDS = 180.0


def _float_attr(marker, name: str) -> float:
    raw = marker.get_attribute(name)
    try:
        value = float(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(f"Profiler attribute {name} is not numeric: {raw!r}") from exc
    if value < 0:
        raise BrowserQAFailure(f"Profiler attribute {name} is negative: {value}")
    return value


def _bool_attr(marker, name: str) -> bool:
    raw = str(marker.get_attribute(name) or "").strip().lower()
    if raw not in {"true", "false"}:
        raise BrowserQAFailure(f"Profiler attribute {name} is not boolean: {raw!r}")
    return raw == "true"


def _wait_for_profiled_deployment(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_READY_BUDGET_SECONDS
    last_error = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            if frame.locator(PROFILE_DEPLOYMENT_SELECTOR).count() > 0:
                print("WNBA_PRA_SPEED_V3_STEP1_DEPLOYMENT_READY_GREEN")
                print(f"WNBA_PRA_SPEED_V3_STEP1_DEPLOYMENT_WAIT_SECONDS={time.monotonic() - started:.3f}")
                return frame, slate_seconds
            last_error = "Step-1 deployment marker absent"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{str(exc)[:400]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)
    raise BrowserQAFailure(
        f"PickVault did not expose the Step-1 profiler deployment within "
        f"{DEPLOYMENT_READY_BUDGET_SECONDS:.0f}s; last={last_error}"
    )


def _wait_profile_marker(page, timeout_seconds: float = 15.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=min(8.0, max(2.0, deadline - time.monotonic())))
        marker = frame.locator(PROFILE_SELECTOR)
        if marker.count() > 0:
            return frame, marker.first
        page.wait_for_timeout(250)
    raise BrowserQAFailure("PRA Speed V3 Step-1 profiler marker did not appear.")


def _profile(marker) -> dict[str, Any]:
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
    if values["player_loader_ms"] > values["total_render_ms"] + 5.0:
        raise BrowserQAFailure(f"Profiler loader timing exceeds total render: {values}")

    return values


def _dominant_phase(profile: dict[str, Any]) -> tuple[str, float]:
    phases = {
        "player_loader": float(profile["player_loader_ms"]),
        "post_loader_render": float(profile["post_loader_render_ms"]),
        "consumer_read": float(profile["consumer_read_ms"]),
        "history_read": float(profile["history_read_ms"]),
        "decision_card": float(profile["decision_card_ms"]),
        "history_summary": float(profile["history_summary_ms"]),
    }
    name = max(phases, key=phases.get)
    return name, phases[name]


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds = _wait_for_profiled_deployment(page)
            frame = _ensure_game_on_slate(page, frame)

            game_started = time.monotonic()
            _game_button(frame).first.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=GAME_READY_BUDGET_SECONDS)
            game_seconds = time.monotonic() - game_started

            player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if player_buttons.count() < 1:
                raise BrowserQAFailure("No Player PRA button available for profiling.")

            player_started = time.monotonic()
            player_buttons.first.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PLAYER_READY_BUDGET_SECONDS)
            player_seconds = time.monotonic() - player_started
            _assert_no_overflow(frame, "player")

            final_ready, missing = _player_final_surfaces_ready(frame)
            if not final_ready:
                raise BrowserQAFailure(f"Frozen Player Intelligence surfaces missing: {missing}")

            frame, marker = _wait_profile_marker(page)
            profile = _profile(marker)
            dominant, dominant_ms = _dominant_phase(profile)

            print(f"WNBA_PRA_SPEED_V3_STEP1_PUBLIC_PLAYER_READY_SECONDS={player_seconds:.3f}")
            for key in (
                "total_render_ms",
                "player_loader_ms",
                "consumer_read_ms",
                "history_read_ms",
                "decision_card_ms",
                "history_summary_ms",
                "post_loader_render_ms",
            ):
                print(f"WNBA_PRA_SPEED_V3_STEP1_{key.upper()}={profile[key]:.3f}")
            print(f"WNBA_PRA_SPEED_V3_STEP1_NETWORK_READS={profile['network_reads']}")
            print(f"WNBA_PRA_SPEED_V3_STEP1_CONSUMER_SESSION_HIT={str(profile['consumer_session_hit']).lower()}")
            print(f"WNBA_PRA_SPEED_V3_STEP1_HISTORY_SESSION_HIT={str(profile['history_session_hit']).lower()}")
            print(f"WNBA_PRA_SPEED_V3_STEP1_COLD_PAIR_LOADER={str(profile['cold_pair_loader_used']).lower()}")
            print(f"WNBA_PRA_SPEED_V3_STEP1_DOMINANT_PHASE={dominant}")
            print(f"WNBA_PRA_SPEED_V3_STEP1_DOMINANT_PHASE_MS={dominant_ms:.3f}")
            print("WNBA_PRA_SPEED_V3_STEP1_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "1/9",
                "production_url": production_url,
                "status": "GREEN",
                "slate_ready_seconds": round(slate_seconds, 3),
                "game_ready_seconds": round(game_seconds, 3),
                "player_ready_seconds": round(player_seconds, 3),
                "profile": profile,
                "dominant_phase": dominant,
                "dominant_phase_ms": round(dominant_ms, 3),
                "frozen_player_surface_green": True,
            }
            (artifacts / "wnba_pra_speed_v3_step1_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(artifacts / "wnba_pra_speed_v3_step1_profile.png"), full_page=True)
            print("WNBA_PRA_SPEED_V3_STEP1_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP1_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-pra-speed-v3-step1")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
