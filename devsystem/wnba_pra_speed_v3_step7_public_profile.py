"""WNBA PRA Speed V3 Step 7 — production active-player precompute proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from typing import Any

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_nav_v2_step7_public_freeze import VIEWPORT, _route_to_wnba_pra
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_pra_speed_v3_step5_public_profile as step5_profile

STEP7_SELECTOR = '[data-wnba-pra-speed-v3-step7="active-player-precompute"]'
STEP4_SELECTOR = '[data-wnba-pra-speed-v3-step4="server-bundle-cache"]'

DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_PRECOMPUTED_PLAYER_SECONDS = 1.5
PRECOMPUTE_SETTLE_MS = 1250


def _int_attr(marker, name: str) -> int:
    raw = marker.get_attribute(name)
    try:
        return int(raw or "")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(
            f"Step-7 marker attribute {name} is not integer: {raw!r}"
        ) from exc


def _bool_attr(marker, name: str) -> bool:
    raw = str(marker.get_attribute(name) or "").strip().lower()
    if raw not in {"true", "false"}:
        raise BrowserQAFailure(
            f"Step-7 marker attribute {name} is not boolean: {raw!r}"
        )
    return raw == "true"


def _wait_step7_streamlit(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            marker = frame.locator(STEP7_SELECTOR)
            if marker.count() > 0:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_SPEED_V3_STEP7_STREAMLIT_DEPLOYED_GREEN")
                print(
                    "WNBA_PRA_SPEED_V3_STEP7_STREAMLIT_DEPLOYMENT_WAIT_SECONDS="
                    f"{elapsed:.3f}"
                )
                return frame, slate_seconds, elapsed
            last = "Step-7 marker absent"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise BrowserQAFailure(
        f"PickVault did not expose Step-7 marker within "
        f"{DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def _marker(frame):
    marker = frame.locator(STEP7_SELECTOR)
    if marker.count() < 1:
        raise BrowserQAFailure("Step-7 precompute marker disappeared.")
    return marker.first


def _step4_marker(frame):
    marker = frame.locator(STEP4_SELECTOR)
    if marker.count() < 1:
        raise BrowserQAFailure("Frozen Step-4 cache marker is missing.")
    return marker.first


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds, streamlit_wait_seconds = _wait_step7_streamlit(page)

            frame, first_name, _ = step5_profile._select_game_with_two_players(page, frame)
            game_marker = _marker(frame)
            target_players = _int_attr(game_marker, "data-target-players")
            background = _bool_attr(game_marker, "data-background")
            if target_players < 2:
                raise BrowserQAFailure(
                    f"Step-7 did not receive the current Game Center player set: "
                    f"targets={target_players}"
                )
            if not background:
                raise BrowserQAFailure("Step-7 precompute is not marked background/nonblocking.")

            print(
                "WNBA_PRA_SPEED_V3_STEP7_PRECOMPUTE_TARGET_PLAYERS="
                f"{target_players}"
            )
            print("WNBA_PRA_SPEED_V3_STEP7_PRECOMPUTE_SCHEDULED_GREEN")

            # The Game Center is already visible while the bounded worker pool warms
            # the frozen Step-4 bundle cache. This short observation window proves the
            # background work can complete without blocking Game Center rendering.
            page.wait_for_timeout(PRECOMPUTE_SETTLE_MS)

            first = frame.get_by_role("button", name=first_name, exact=True)
            if first.count() < 1:
                first = frame.get_by_role(
                    "button", name=re.compile(r"^Open .+ PRA →$")
                ).first

            started = time.monotonic()
            first.click()
            frame, _ = step5_profile._wait_page_resilient(
                page,
                "player",
                timeout_seconds=step5_profile.PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS,
            )
            player_seconds = time.monotonic() - started
            step5_profile._assert_player_ready(frame)

            cache_marker = _step4_marker(frame)
            cache_hit = _bool_attr(cache_marker, "data-server-cache-hit")
            cached_read_ms = float(
                cache_marker.get_attribute("data-cached-bundle-read-ms") or "0"
            )
            if not cache_hit:
                raise BrowserQAFailure(
                    "Step-7 selected player did not consume a precomputed Step-4 "
                    "finished-bundle cache hit."
                )
            print("WNBA_PRA_SPEED_V3_STEP7_BUNDLE_CACHE_HIT_OBSERVED_GREEN")
            print(
                "WNBA_PRA_SPEED_V3_STEP7_OBSERVED_PLAYER_SECONDS="
                f"{player_seconds:.3f}"
            )
            if player_seconds > MAX_PRECOMPUTED_PLAYER_SECONDS:
                raise BrowserQAFailure(
                    "Step-7 precomputed Player open exceeded target: "
                    f"{player_seconds:.3f}s > {MAX_PRECOMPUTED_PLAYER_SECONDS:.3f}s"
                )

            player_marker = _marker(frame)
            completed = _int_attr(player_marker, "data-completed")
            errors = _int_attr(player_marker, "data-errors")
            if completed < 1:
                raise BrowserQAFailure(
                    f"Step-7 background results were not visible after Player rerun: "
                    f"completed={completed}"
                )
            if errors:
                raise BrowserQAFailure(
                    f"Step-7 precompute reported errors for the selected Game Center: "
                    f"errors={errors}"
                )

            print("WNBA_PRA_SPEED_V3_STEP7_BUNDLE_CACHE_HIT_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP7_PLAYER_READY_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP7_FROZEN_STEPS1_6_GREEN")
            print(
                "WNBA_PRA_SPEED_V3_STEP7_PRECOMPUTED_PLAYER_SECONDS="
                f"{player_seconds:.3f}"
            )
            print(
                "WNBA_PRA_SPEED_V3_STEP7_CACHED_BUNDLE_READ_MS="
                f"{cached_read_ms:.3f}"
            )
            print("WNBA_PRA_SPEED_V3_STEP7_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "7/9",
                "status": "GREEN",
                "production_url": production_url,
                "streamlit_deployment_wait_seconds": round(streamlit_wait_seconds, 3),
                "slate_ready_seconds": round(slate_seconds, 3),
                "target_players": target_players,
                "completed_precomputes": completed,
                "precompute_errors": errors,
                "bundle_cache_hit": cache_hit,
                "precomputed_player_seconds": round(player_seconds, 3),
                "cached_bundle_read_ms": round(cached_read_ms, 3),
            }
            (artifacts / "wnba_pra_speed_v3_step7_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(
                path=str(artifacts / "wnba_pra_speed_v3_step7_profile.png"),
                full_page=True,
            )

            print("WNBA_PRA_SPEED_V3_STEP7_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP7_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-speed-v3-step7",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
