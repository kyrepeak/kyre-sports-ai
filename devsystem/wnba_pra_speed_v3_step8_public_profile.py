"""WNBA PRA Speed V3 Step 8 — production visible-first render proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_nav_v2_step7_public_freeze import VIEWPORT, _route_to_wnba_pra
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_pra_speed_v3_step5_public_profile as step5_profile

STEP8_SELECTOR = '[data-wnba-pra-speed-v3-step8="visible-first"][data-active="true"]'
SHELL_SELECTOR = '[data-wnba-pra-speed-v3-step8-shell="visible"]'
FINAL_HERO_SELECTOR = ".wn4-hero"
RESULT_SELECTOR = '[data-wnba-pra-speed-v3-step8-result="true"]'
STEP7_SELECTOR = '[data-wnba-pra-speed-v3-step7="active-player-precompute"]'

DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_VISIBLE_SHELL_SECONDS = 0.75
MAX_FINAL_PLAYER_SECONDS = 1.50
DIAGNOSTIC_MAX_SECONDS = 2.50
PRECOMPUTE_SETTLE_MS = 1250


def _bool_attr(marker, name: str) -> bool:
    raw = str(marker.get_attribute(name) or "").strip().lower()
    if raw not in {"true", "false"}:
        raise BrowserQAFailure(
            f"Step-8 marker attribute {name} is not boolean: {raw!r}"
        )
    return raw == "true"


def _float_attr(marker, name: str) -> float:
    raw = marker.get_attribute(name)
    try:
        return float(raw or "0")
    except (TypeError, ValueError) as exc:
        raise BrowserQAFailure(
            f"Step-8 marker attribute {name} is not numeric: {raw!r}"
        ) from exc


def _visible_step8_surface(page):
    """Return the current Streamlit frame and first visible Step-8 surface."""
    for candidate in page.frames:
        try:
            shell = candidate.locator(SHELL_SELECTOR).first
            if shell.count() > 0 and shell.is_visible():
                return candidate, "shell"
        except Exception:
            pass
        try:
            final_hero = candidate.locator(FINAL_HERO_SELECTOR).first
            if final_hero.count() > 0 and final_hero.is_visible():
                return candidate, "final"
        except Exception:
            pass
    return None, ""


def _measure_first_visible_content(page, started: float, max_seconds: float):
    """Measure the first visible Step-8 user surface across Streamlit reruns."""
    deadline = float(started) + float(max_seconds)
    while time.monotonic() < deadline:
        frame, visible_path = _visible_step8_surface(page)
        if frame is not None and visible_path:
            return frame, visible_path, time.monotonic() - float(started)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        page.wait_for_timeout(min(25, max(1, int(remaining * 1000))))
    return None, "", time.monotonic() - float(started)


def _wait_first_visible_content(page, started: float):
    """Freeze gate: first visible Player content must arrive within 0.750s."""
    frame, visible_path, visible_seconds = _measure_first_visible_content(
        page,
        started,
        MAX_VISIBLE_SHELL_SECONDS,
    )
    if frame is not None and visible_path and visible_seconds <= MAX_VISIBLE_SHELL_SECONDS:
        return frame, visible_path, visible_seconds

    raise BrowserQAFailure(
        "Step-8 neither temporary shell nor final Player hero became visible "
        f"across the Streamlit rerun within target: {MAX_VISIBLE_SHELL_SECONDS:.3f}s"
    )


def _wait_step8_streamlit(page):
    started = time.monotonic()
    deadline = started + DEPLOYMENT_WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        try:
            frame, slate_seconds = _route_to_wnba_pra(page)
            marker = frame.locator(STEP8_SELECTOR)
            if marker.count() > 0:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_SPEED_V3_STEP8_STREAMLIT_DEPLOYED_GREEN")
                print(
                    "WNBA_PRA_SPEED_V3_STEP8_STREAMLIT_DEPLOYMENT_WAIT_SECONDS="
                    f"{elapsed:.3f}"
                )
                return frame, slate_seconds, elapsed
            last = "Step-8 visible-first deployment marker absent"
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise BrowserQAFailure(
        f"PickVault did not expose Step-8 marker within "
        f"{DEPLOYMENT_WAIT_SECONDS:.0f}s; last={last}"
    )


def run(*, production_url: str, artifact_dir: str | Path, diagnostic_first_visible: bool = False) -> dict[str, Any]:
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
            frame, slate_seconds, deploy_seconds = _wait_step8_streamlit(page)
            frame, first_name, _ = step5_profile._select_game_with_two_players(page, frame)

            if frame.locator(STEP7_SELECTOR).count() < 1:
                raise BrowserQAFailure("Frozen Step-7 precompute marker is missing under Step 8.")

            page.wait_for_timeout(PRECOMPUTE_SETTLE_MS)
            first = frame.get_by_role("button", name=first_name, exact=True)
            if first.count() < 1:
                first = frame.get_by_role("button", name="Open", exact=False).first

            started = time.monotonic()
            first.click()

            if diagnostic_first_visible:
                frame, visible_path, visible_seconds = _measure_first_visible_content(
                    page,
                    started,
                    DIAGNOSTIC_MAX_SECONDS,
                )
                target_met = bool(
                    frame is not None
                    and visible_path
                    and visible_seconds <= MAX_VISIBLE_SHELL_SECONDS
                )
                print("WNBA_PRA_SPEED_V3_STEP8_DIAGNOSTIC_ONLY")
                print(
                    "WNBA_PRA_SPEED_V3_STEP8_DIAGNOSTIC_FIRST_VISIBLE_SECONDS="
                    f"{visible_seconds:.3f}"
                )
                print(
                    "WNBA_PRA_SPEED_V3_STEP8_DIAGNOSTIC_FIRST_VISIBLE_PATH="
                    f"{visible_path or 'none'}"
                )
                print(
                    "WNBA_PRA_SPEED_V3_STEP8_DIAGNOSTIC_075_TARGET_MET="
                    f"{str(target_met).lower()}"
                )
                final_frame, _ = step5_profile._wait_page_resilient(
                    page,
                    "player",
                    timeout_seconds=step5_profile.PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS,
                )
                final_seconds = time.monotonic() - started
                step5_profile._assert_player_ready(final_frame)
                print(
                    "WNBA_PRA_SPEED_V3_STEP8_DIAGNOSTIC_FINAL_PLAYER_SECONDS="
                    f"{final_seconds:.3f}"
                )
                result = {
                    "project": "WNBA PRA Speed V3",
                    "step": "8/9",
                    "status": "DIAGNOSTIC_ONLY",
                    "production_url": production_url,
                    "visible_target_seconds": MAX_VISIBLE_SHELL_SECONDS,
                    "diagnostic_max_seconds": DIAGNOSTIC_MAX_SECONDS,
                    "first_visible_seconds": round(visible_seconds, 3),
                    "first_visible_path": visible_path or "none",
                    "visible_target_met": target_met,
                    "final_player_seconds": round(final_seconds, 3),
                }
                (artifacts / "wnba_pra_speed_v3_step8_diagnostic.json").write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                page.screenshot(
                    path=str(artifacts / "wnba_pra_speed_v3_step8_diagnostic.png"),
                    full_page=True,
                )
                print("WNBA_PRA_SPEED_V3_STEP8_DIAGNOSTIC_COMPLETE")
                return result

            frame, visible_path, visible_seconds = _wait_first_visible_content(
                page,
                started,
            )
            print(
                "WNBA_PRA_SPEED_V3_STEP8_VISIBLE_CONTENT_SECONDS="
                f"{visible_seconds:.3f}"
            )
            print(
                "WNBA_PRA_SPEED_V3_STEP8_VISIBLE_CONTENT_PATH="
                f"{visible_path}"
            )
            print("WNBA_PRA_SPEED_V3_STEP8_FRAME_REACQUIRE_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_VISIBLE_CONTENT_GREEN")

            frame, _ = step5_profile._wait_page_resilient(
                page,
                "player",
                timeout_seconds=step5_profile.PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS,
            )
            final_seconds = time.monotonic() - started
            step5_profile._assert_player_ready(frame)
            if final_seconds > MAX_FINAL_PLAYER_SECONDS:
                raise BrowserQAFailure(
                    "Step-8 final Player exceeded preserved cached-cold target: "
                    f"{final_seconds:.3f}s > {MAX_FINAL_PLAYER_SECONDS:.3f}s"
                )

            marker = frame.locator(RESULT_SELECTOR)
            if marker.count() < 1:
                raise BrowserQAFailure("Step-8 final result marker is missing.")
            marker = marker.first
            shell_emitted = _bool_attr(marker, "data-shell-emitted")
            shell_before_loader = _bool_attr(marker, "data-shell-before-loader")
            shell_removed = _bool_attr(marker, "data-shell-removed-before-final")
            shell_retained = _bool_attr(marker, "data-shell-retained-through-final")
            shell_emit_ms = _float_attr(marker, "data-shell-emit-ms")
            loader_ms = _float_attr(marker, "data-loader-ms")
            if (
                not shell_emitted
                or not shell_before_loader
                or not shell_retained
                or shell_removed
            ):
                raise BrowserQAFailure(
                    "Step-8 visible-first shell lifetime contract was not preserved."
                )

            print("WNBA_PRA_SPEED_V3_STEP8_VISIBLE_SHELL_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_SHELL_BEFORE_LOADER_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_SHELL_LIFETIME_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_FINAL_PLAYER_READY_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_FROZEN_STEPS1_7_GREEN")
            print(
                "WNBA_PRA_SPEED_V3_STEP8_FINAL_PLAYER_SECONDS="
                f"{final_seconds:.3f}"
            )
            print(
                "WNBA_PRA_SPEED_V3_STEP8_SHELL_EMIT_MS="
                f"{shell_emit_ms:.3f}"
            )
            print(
                "WNBA_PRA_SPEED_V3_STEP8_FROZEN_LOADER_MS="
                f"{loader_ms:.3f}"
            )
            print("WNBA_PRA_SPEED_V3_STEP8_PROFILE_GREEN")

            result = {
                "project": "WNBA PRA Speed V3",
                "step": "8/9",
                "status": "GREEN",
                "production_url": production_url,
                "streamlit_deployment_wait_seconds": round(deploy_seconds, 3),
                "slate_ready_seconds": round(slate_seconds, 3),
                "visible_content_seconds": round(visible_seconds, 3),
                "visible_content_path": visible_path,
                "visible_shell_seconds": round(visible_seconds, 3) if visible_path == "shell" else None,
                "final_player_seconds": round(final_seconds, 3),
                "shell_emitted": shell_emitted,
                "shell_before_loader": shell_before_loader,
                "shell_removed_before_final": shell_removed,
                "shell_retained_through_final": shell_retained,
                "shell_emit_ms": round(shell_emit_ms, 3),
                "frozen_loader_ms": round(loader_ms, 3),
            }
            (artifacts / "wnba_pra_speed_v3_step8_profile.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(
                path=str(artifacts / "wnba_pra_speed_v3_step8_profile.png"),
                full_page=True,
            )
            print("WNBA_PRA_SPEED_V3_STEP8_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-speed-v3-step8",
    )
    parser.add_argument(
        "--diagnostic-first-visible",
        action="store_true",
        help="Measure first-visible timing up to 2.50s without certifying Step 8.",
    )
    args = parser.parse_args()
    run(
        production_url=args.production_url,
        artifact_dir=args.artifact_dir,
        diagnostic_first_visible=args.diagnostic_first_visible,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
