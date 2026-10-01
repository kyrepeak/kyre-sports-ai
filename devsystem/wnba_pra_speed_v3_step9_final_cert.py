"""WNBA PRA Speed V3 Step 9 — final strict production speed certification.

Certification-only owner. It composes the already-frozen Step-5 and Step-8
production profiles and fails closed if any final latency budget regresses.
No WNBA product/runtime/model/provider/router/math behavior is modified here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_pra_speed_v3_step5_public_profile as step5_profile
from devsystem import wnba_pra_speed_v3_step8_public_profile as step8_profile

WARM_SAME_SESSION_SECONDS_MAX = 0.75
CACHED_COLD_SECONDS_MAX = 1.50
TRUE_COLD_SECONDS_MAX = 2.50
VISIBLE_CONTINUITY_SECONDS_MAX = 0.75

PROJECT = "WNBA PRA Speed V3"
STEP = "9/9"


def _bounded(label: str, value: float, limit: float) -> float:
    observed = float(value)
    if observed < 0:
        raise BrowserQAFailure(f"{label} timing is negative: {observed:.3f}s")
    if observed > float(limit):
        raise BrowserQAFailure(
            f"Step-9 {label} exceeded final budget: "
            f"{observed:.3f}s > {float(limit):.3f}s"
        )
    return observed


def certify_results(
    *,
    step5_result: dict[str, Any],
    step8_result: dict[str, Any],
) -> dict[str, Any]:
    if step5_result.get("status") != "GREEN":
        raise BrowserQAFailure("Frozen Step-5 production profile is not GREEN.")
    if step8_result.get("status") != "GREEN":
        raise BrowserQAFailure("Frozen Step-8 production profile is not GREEN.")
    if step5_result.get("project") != PROJECT or step8_result.get("project") != PROJECT:
        raise BrowserQAFailure("Final certification received a foreign project result.")

    true_cold = _bounded(
        "true-cold Player",
        step5_result["true_cold_player_seconds"],
        TRUE_COLD_SECONDS_MAX,
    )
    warm = _bounded(
        "warm same-session Player",
        step5_result["warm_same_session_seconds"],
        WARM_SAME_SESSION_SECONDS_MAX,
    )
    cached = _bounded(
        "cached-cold Player",
        step8_result["final_player_seconds"],
        CACHED_COLD_SECONDS_MAX,
    )
    visible = _bounded(
        "browser-resident visible continuity",
        step8_result["visible_content_seconds"],
        VISIBLE_CONTINUITY_SECONDS_MAX,
    )

    if step8_result.get("visible_content_path") not in {
        "game_card_continuity",
        "client_preview",
    }:
        raise BrowserQAFailure(
            "Step-9 final proof requires the frozen Step-8 browser-resident "
            "continuity path before the Streamlit rerun."
        )
    if step8_result.get("frozen_steps_1_7_preserved") is not True:
        raise BrowserQAFailure("Step-8 did not certify frozen Steps 1-7 preservation.")
    if step8_result.get("server_shell_runtime_fallback_preserved") is not True:
        raise BrowserQAFailure("Step-8 server-shell fallback preservation is missing.")

    return {
        "project": PROJECT,
        "step": STEP,
        "status": "GREEN",
        "warm_same_session_seconds": round(warm, 3),
        "warm_same_session_seconds_max": WARM_SAME_SESSION_SECONDS_MAX,
        "cached_cold_seconds": round(cached, 3),
        "cached_cold_seconds_max": CACHED_COLD_SECONDS_MAX,
        "true_cold_seconds": round(true_cold, 3),
        "true_cold_seconds_max": TRUE_COLD_SECONDS_MAX,
        "visible_continuity_seconds": round(visible, 3),
        "visible_continuity_seconds_max": VISIBLE_CONTINUITY_SECONDS_MAX,
        "visible_continuity_path": step8_result["visible_content_path"],
        "step5_profile_green": True,
        "step8_profile_green": True,
        "frozen_steps_1_8_preserved": True,
        "product_runtime_changed_by_step9": False,
        "projection_math_changed_by_step9": False,
        "market_math_changed_by_step9": False,
        "data_meaning_changed_by_step9": False,
        "sportsbook_projection_influence_changed_by_step9": False,
    }


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # True-cold + warm same-session proof runs first in a fresh browser context.
    step5_result = step5_profile.run(
        production_url=production_url,
        artifact_dir=artifacts / "step5-final-proof",
    )

    # Cached-cold + browser-resident visible-first proof runs second and requires
    # the frozen Step-7 precompute readiness gate before timing.
    step8_result = step8_profile.run(
        production_url=production_url,
        artifact_dir=artifacts / "step8-final-proof",
    )

    result = certify_results(
        step5_result=step5_result,
        step8_result=step8_result,
    )
    (artifacts / "wnba_pra_speed_v3_step9_final_cert.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "WNBA_PRA_SPEED_V3_STEP9_TRUE_COLD_SECONDS="
        f"{result['true_cold_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_WARM_SAME_SESSION_SECONDS="
        f"{result['warm_same_session_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_CACHED_COLD_SECONDS="
        f"{result['cached_cold_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_SECONDS="
        f"{result['visible_continuity_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_PATH="
        f"{result['visible_continuity_path']}"
    )
    print("WNBA_PRA_SPEED_V3_STEP9_TRUE_COLD_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_WARM_SAME_SESSION_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_CACHED_COLD_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_FROZEN_STEPS1_8_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_PROFILE_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_FROZEN")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-speed-v3-step9",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
