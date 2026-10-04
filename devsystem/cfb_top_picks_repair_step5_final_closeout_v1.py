"""CFB Top Picks Repair Mission Step 5/5 — final proof-only closeout.

This verifier composes the already-frozen Step 1/2 repository contracts with
fresh Step 3/4 live proof, then delegates responsive/public browser proof to the
existing Step-5 visual cert in CI. It does not mutate product behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import cfb_top_picks_details_v5 as details_v5
import cfb_top_picks_page_v9 as page_v9
from devsystem import cfb_top_picks_defense_pace_repair_step2_v1 as step2
from devsystem import cfb_top_picks_history_router_repair_step1_v1 as step1
from devsystem import cfb_top_picks_market_reasoning_repair_step3_v1 as step3
from devsystem import cfb_top_picks_repair_step4_detail_integrity_v1 as step4
from devsystem import cfb_top_picks_step5_visual_cert_v1 as visual

MODEL_VERSION = "CFB TOP PICKS REPAIR STEP 5 • FINAL CLOSEOUT CERT"
MISSION_STEP = "5/5"
PUBLIC_URL = "https://pickvault.streamlit.app"

REQUIRED_REPAIR_STEPS = (
    "MATCHUP_HISTORY_ROUTER",
    "DEFENSE_PACE_COMPLETENESS",
    "MARKET_AWARE_FOOTBALL_REASONING",
    "DETAIL_INTEGRITY",
)
REQUIRED_VIEWPORTS = ((390, 844), (768, 1024), (1440, 1000))
REQUIRED_DETAIL_SECTIONS = (
    "Why This Pick",
    "Actual Matchup History",
    "Benefits",
    "Market-Aware Football Reasoning",
)

API2_USED = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
HISTORY_PROJECTION_WEIGHT = 0.0
HISTORY_SELECTION_WEIGHT = 0.0
HISTORY_RANKING_WEIGHT = 0.0
MAY_MODIFY_PAGE = False
MAY_MODIFY_ROUTER = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SPORTSBOOK = False


def _require_green(payload: Mapping[str, Any], token: str) -> None:
    if str(payload.get("status") or "").upper() != "GREEN":
        raise AssertionError(token)


def verify_repository_contract() -> dict[str, Any]:
    """Fail closed if any frozen repair contract or final visual owner drifts."""
    step1_result = step1.check_repository()
    step2_result = step2.check_repository()
    _require_green(step1_result, "STEP5_STEP1_CONTRACT_NOT_GREEN")
    _require_green(step2_result, "STEP5_STEP2_CONTRACT_NOT_GREEN")

    current_v9_page = bool(getattr(page_v9, "PAGE_MARKER", "")) and callable(
        getattr(page_v9, "_detail_card", None)
    )
    current_v5_detail_builder = callable(getattr(details_v5, "build_pick_detail", None))
    step3_contract = (
        step3.MISSION_STEP == "3/5"
        and step3.API2_USED is False
        and callable(getattr(step3, "run_live", None))
    )
    step4_contract = (
        step4.MISSION_STEP == "4/5"
        and step4.API2_USED is False
        and callable(getattr(step4, "run_live", None))
        and tuple(step4.REQUIRED_SECTIONS) == REQUIRED_DETAIL_SECTIONS[:3]
    )
    legacy_step5_visual_contract = (
        tuple(visual.WIDTHS) == REQUIRED_VIEWPORTS
        and visual.PUBLIC_URL == PUBLIC_URL
        and visual.ROOT.startswith('[data-testid="cfb-top-picks-step5-root"')
    )

    checks = {
        "current_v9_page": current_v9_page,
        "current_v5_detail_builder": current_v5_detail_builder,
        "step1_contract": True,
        "step2_contract": True,
        "step3_contract": step3_contract,
        "step4_contract": step4_contract,
        "legacy_step5_visual_contract": legacy_step5_visual_contract,
    }
    failed = [name for name, value in checks.items() if value is not True]
    if failed:
        raise AssertionError("STEP5_REPOSITORY_CONTRACT_DRIFT:" + ",".join(failed))

    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        **checks,
        "public_host": PUBLIC_URL,
        "required_viewports": [list(item) for item in REQUIRED_VIEWPORTS],
        "api2_used": False,
        "product_mutation": False,
    }


def _finalize_live_payload(
    step3_payload: Mapping[str, Any], step4_payload: Mapping[str, Any]
) -> dict[str, Any]:
    _require_green(step3_payload, "STEP5_STEP3_NOT_GREEN")
    if int(step3_payload.get("ranked_picks_certified") or 0) != 10:
        raise AssertionError("STEP5_STEP3_NOT_10_OF_10")
    if step3_payload.get("all_reasoning_usable") is not True:
        raise AssertionError("STEP5_STEP3_REASONING_NOT_USABLE")

    _require_green(step4_payload, "STEP5_STEP4_NOT_GREEN")
    if int(step4_payload.get("ranked_picks_certified") or 0) != 10:
        raise AssertionError("STEP5_STEP4_NOT_10_OF_10")
    if step4_payload.get("selected_matchup_detail_contract") is not True:
        raise AssertionError("STEP5_STEP4_DETAIL_CONTRACT_NOT_GREEN")

    for payload, prefix in ((step3_payload, "STEP3"), (step4_payload, "STEP4")):
        for key in ("projection_changed", "probability_changed", "ranking_changed", "selection_changed"):
            if payload.get(key) is not False:
                raise AssertionError(f"STEP5_{prefix}_{key.upper()}")
        if float(payload.get("sportsbook_projection_weight") or 0.0) != 0.0:
            raise AssertionError(f"STEP5_{prefix}_SPORTSBOOK_WEIGHT")
        if payload.get("api2_used") is not False:
            raise AssertionError(f"STEP5_{prefix}_API2_USED")

    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "ranked_picks_certified": 10,
        "step1_history_router_green": True,
        "step2_defense_pace_green": True,
        "step3_market_reasoning_green": True,
        "step4_detail_integrity_green": True,
        "projection_changed": False,
        "probability_changed": False,
        "ranking_changed": False,
        "selection_changed": False,
        "sportsbook_projection_weight": 0.0,
        "history_projection_weight": 0.0,
        "history_selection_weight": 0.0,
        "history_ranking_weight": 0.0,
        "api2_used": False,
        "public_proof_required_before_freeze": True,
        "required_viewports": [list(item) for item in REQUIRED_VIEWPORTS],
        "required_detail_sections": list(REQUIRED_DETAIL_SECTIONS),
    }


def run_live(
    artifact_dir: str | Path = "artifacts/cfb-top-picks-repair-step5-final-closeout",
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    repository_contract = verify_repository_contract()
    step3_payload = step3.run_live(artifacts / "step3")
    step4_payload = step4.run_live(artifacts / "step4")
    payload = _finalize_live_payload(step3_payload, step4_payload)
    payload["repository_contract"] = repository_contract

    (artifacts / "live_step5_final_closeout.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("CFB_TOP_PICKS_REPAIR_STEP5_REPAIRED_STACK_GREEN")
    print("CFB_TOP_PICKS_REPAIR_STEP5_FINAL_CLOSEOUT_GREEN")
    print("CFB_TOP_PICKS_REPAIR_STEPS1_5_READY_FOR_PUBLIC_FREEZE")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    run_live()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
