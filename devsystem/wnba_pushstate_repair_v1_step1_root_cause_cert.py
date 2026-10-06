"""Runless source cert for WNBA pushState Repair V1 Step 1.

Diagnosis only. This cert proves the current production source contains the
self-retriggering query-param writer responsible for the browser history loop.
It intentionally does not patch product/runtime behavior; Step 2 owns the fix.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
NAVIGATION = ROOT / "wnba_pra_navigation_v2_step1.py"

OWNER = "_pin_deep_wnba_shell_route"


def diagnose() -> dict[str, object]:
    overlay = OVERLAY.read_text(encoding="utf-8")
    navigation = NAVIGATION.read_text(encoding="utf-8")

    owner_present = f"def {OWNER}(" in overlay
    unconditional_sport_write = (
        "st.query_params[SHELL_SPORT_QUERY_KEY] = SHELL_SPORT_VALUE" in overlay
    )
    unconditional_market_write = (
        "st.query_params[SHELL_MARKET_QUERY_KEY] = SHELL_MARKET_VALUE" in overlay
    )
    render_time_pin = "\n    _pin_deep_wnba_shell_route()\n" in overlay
    wrapped_nav_writer = all(
        token in overlay
        for token in (
            "def stable_nav_query_writer(state):",
            "result = original_nav_query_writer(state)",
            "_pin_deep_wnba_shell_route(state)",
            "navigation._write_query = stable_nav_query_writer",
        )
    )
    navigation_query_writer = all(
        token in navigation
        for token in (
            "st.query_params[QUERY_PAGE] = state.page",
            "st.query_params[QUERY_GAME] = state.game_id",
            "st.query_params[QUERY_PLAYER] = state.player_id",
        )
    )

    feedback_loop_proven = all(
        (
            owner_present,
            unconditional_sport_write,
            unconditional_market_write,
            render_time_pin,
            wrapped_nav_writer,
            navigation_query_writer,
        )
    )

    return {
        "step": "1/4",
        "scope": "root_cause_diagnosis_only",
        "owner": OWNER,
        "owner_file": OVERLAY.name,
        "owner_present": owner_present,
        "unconditional_shell_query_writes": bool(
            unconditional_sport_write and unconditional_market_write
        ),
        "render_time_pin": render_time_pin,
        "wrapped_navigation_query_writer": wrapped_nav_writer,
        "frozen_navigation_writer_present": navigation_query_writer,
        "feedback_loop_proven": feedback_loop_proven,
        "product_runtime_patch_in_step1": False,
        "next_step": "Step 2: make shell query persistence idempotent with one surgical patch",
    }


def main() -> int:
    report = diagnose()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["feedback_loop_proven"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
