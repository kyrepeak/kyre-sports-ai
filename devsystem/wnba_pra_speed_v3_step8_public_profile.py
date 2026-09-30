"""WNBA PRA Speed V3 Step 8 — production visible-first render proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_nav_v2_step7_public_freeze import VIEWPORT, _route_to_wnba_pra
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_pra_speed_v3_step5_public_profile as step5_profile

STEP8_SELECTOR = '[data-wnba-pra-speed-v3-step8="visible-first"][data-active="true"]'
SHELL_SELECTOR = '[data-wnba-pra-speed-v3-step8-shell="visible"]'
RESULT_SELECTOR = '[data-wnba-pra-speed-v3-step8-result="true"]'
STEP7_SELECTOR = '[data-wnba-pra-speed-v3-step7="active-player-precompute"]'

DEPLOYMENT_WAIT_SECONDS = 600.0
MAX_VISIBLE_SHELL_SECONDS = 0.75
MAX_FINAL_PLAYER_SECONDS = 1.50
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


def _arm_shell_mutation_observer(frame) -> float:
    """Observe the ephemeral Step-8 shell even if it is removed before locator polling."""
    armed_at = frame.evaluate(
        """selector => {
            if (window.__ksStep8ShellObserver &&
                typeof window.__ksStep8ShellObserver.disconnect === "function") {
                window.__ksStep8ShellObserver.disconnect();
            }
            window.__ksStep8ShellObservedAt = null;
            const containsShell = (node) => {
                if (!node) return false;
                if (node.nodeType === Node.ELEMENT_NODE &&
                    typeof node.matches === "function" &&
                    node.matches(selector)) {
                    return true;
                }
                return typeof node.querySelector === "function" &&
                    node.querySelector(selector) !== null;
            };
            const observer = new MutationObserver((records) => {
                for (const record of records) {
                    for (const node of record.addedNodes) {
                        if (containsShell(node)) {
                            window.__ksStep8ShellObservedAt = performance.now();
                            observer.disconnect();
                            return;
                        }
                    }
                }
            });
            observer.observe(document.documentElement, {
                childList: true,
                subtree: true,
            });
            window.__ksStep8ShellObserver = observer;
            return performance.now();
        }""",
        SHELL_SELECTOR,
    )
    return float(armed_at or 0.0)


def _wait_shell_mutation(frame, armed_at_ms: float) -> float:
    try:
        frame.wait_for_function(
            "() => Number.isFinite(window.__ksStep8ShellObservedAt)",
            timeout=int(MAX_VISIBLE_SHELL_SECONDS * 1000),
        )
    except PlaywrightTimeoutError as exc:
        raise BrowserQAFailure(
            "Step-8 visible Player shell DOM insertion was not observed within target: "
            f"{MAX_VISIBLE_SHELL_SECONDS:.3f}s"
        ) from exc

    observed_at = frame.evaluate("() => window.__ksStep8ShellObservedAt")
    shell_seconds = max(0.0, (float(observed_at) - float(armed_at_ms)) / 1000.0)
    if shell_seconds > MAX_VISIBLE_SHELL_SECONDS:
        raise BrowserQAFailure(
            "Step-8 visible shell exceeded target: "
            f"{shell_seconds:.3f}s > {MAX_VISIBLE_SHELL_SECONDS:.3f}s"
        )
    return shell_seconds


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
            frame, slate_seconds, deploy_seconds = _wait_step8_streamlit(page)
            frame, first_name, _ = step5_profile._select_game_with_two_players(page, frame)

            if frame.locator(STEP7_SELECTOR).count() < 1:
                raise BrowserQAFailure("Frozen Step-7 precompute marker is missing under Step 8.")

            page.wait_for_timeout(PRECOMPUTE_SETTLE_MS)
            first = frame.get_by_role("button", name=first_name, exact=True)
            if first.count() < 1:
                first = frame.get_by_role("button", name="Open", exact=False).first

            started = time.monotonic()
            observer_armed_at_ms = _arm_shell_mutation_observer(frame)
            first.click()
            shell_seconds = _wait_shell_mutation(frame, observer_armed_at_ms)
            print(
                "WNBA_PRA_SPEED_V3_STEP8_VISIBLE_SHELL_SECONDS="
                f"{shell_seconds:.3f}"
            )
            print("WNBA_PRA_SPEED_V3_STEP8_MUTATION_OBSERVER_GREEN")
            print("WNBA_PRA_SPEED_V3_STEP8_VISIBLE_SHELL_GREEN")

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
                "visible_shell_seconds": round(shell_seconds, 3),
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
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
