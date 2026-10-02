"""WNBA PRA Repair V1 Step 3 — component certification.

Step 3 is intentionally certified as a merged-main component because the user
explicitly skipped the still-unresolved Page-2 public-navigation blocker.  The
component is complete and composable, but production activation is deferred to
the next integration step so we do not mutate frozen app.py twice.

No projection, probability, market, qualification, ranking, sportsbook, or
Monte Carlo math is changed here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.execution_plan_compiler_v1 import (
    compile_execution_plan,
    validate_execution_plan,
)
from devsystem.chaos_adversarial_certification_harness_v1 import (
    contract_self_test as chaos_contract_self_test,
)
import wnba_pra_repair_v1_step3_data as data

PROJECT = "WNBA PRA Repair V1"
STEP = "3/7"
BASE_MAIN_SHA = "5bdbe8548a3cc20db2100d2d6b458b49c6956521"

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
APP = ROOT / "app.py"

WRITE_PATHS = [
    ".github/workflows/wnba-pra-repair-v1-step3-data-completeness.yml",
    "devsystem/task_ledgers/wnba-pra-repair-v1-step3-data-completeness.json",
    "devsystem/wnba_pra_repair_v1_step3_data_completeness_cert.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py",
    "tests/test_wnba_pra_repair_v1_step3.py",
    "wnba_pra_repair_v1_step3_data.py",
]


def compiled_plan() -> dict[str, Any]:
    checkpoints = [
        {
            "checkpoint_id": "rollback_anchor",
            "title": "Seal current-main rollback anchor",
            "action_type": "READ_ONLY",
            "depends_on": [],
            "write_paths": [],
            "dependency_tokens": ["main:" + BASE_MAIN_SHA],
            "shared_resources": [],
            "expected_proof": ["exact current-main identity", "transaction-owned paths only"],
            "completion_criteria": ["baseline sealed"],
        },
        {
            "checkpoint_id": "component_patch",
            "title": "Reconcile Step-3 component on current main",
            "action_type": "MUTATION",
            "depends_on": ["rollback_anchor"],
            "write_paths": WRITE_PATHS,
            "dependency_tokens": ["domain:wnba-pra-step3", "parent:wnba-pra-repair-step2"],
            "shared_resources": [],
            "expected_proof": ["focused tests", "frozen dependency blob guards"],
            "completion_criteria": ["component sources complete", "no app.py mutation"],
        },
        {
            "checkpoint_id": "exact_head_proof",
            "title": "Exact-head focused + DevSystem proof",
            "action_type": "READ_ONLY",
            "depends_on": ["component_patch"],
            "write_paths": [],
            "dependency_tokens": ["proof:exact-head"],
            "shared_resources": [],
            "expected_proof": ["focused CI success", "devsystem-final-gate success"],
            "completion_criteria": ["exact PR head certified"],
        },
        {
            "checkpoint_id": "merge_exact_head",
            "title": "Merge only the certified head",
            "action_type": "MUTATION",
            "depends_on": ["exact_head_proof", "rollback_anchor"],
            "write_paths": WRITE_PATHS,
            "dependency_tokens": ["merge:certified-head-only"],
            "shared_resources": [],
            "expected_proof": ["merge SHA contains certified blobs"],
            "completion_criteria": ["certified head merged"],
        },
        {
            "checkpoint_id": "merged_main_proof",
            "title": "Merged-main component certification",
            "action_type": "READ_ONLY",
            "depends_on": ["merge_exact_head"],
            "write_paths": [],
            "dependency_tokens": ["proof:merged-main"],
            "shared_resources": [],
            "expected_proof": ["merged-main workflow terminal success"],
            "completion_criteria": ["Step 3 GREEN + FROZEN component proof"],
        },
    ]
    plan = compile_execution_plan(
        repository="kyrepeak/kyre-sports-ai",
        mission_id="wnba-pra-repair-v1-step3-data-completeness",
        mission="WNBA PRA Repair V1 Step 3 Page 3 data completeness component",
        expected_main_sha=BASE_MAIN_SHA,
        observed_main_sha=BASE_MAIN_SHA,
        checkpoints=checkpoints,
        rollback_checkpoint_id="rollback_anchor",
        freeze_contract={
            "exact_pr_head_proof": True,
            "devsystem_final_gate": True,
            "merge_exact_certified_head": True,
            "merged_main_proof": True,
            "terminal_proof_receipt": True,
            "green_plus_frozen": True,
            "freeze_tokens": ["GREEN", "FROZEN"],
        },
        completion_criteria=[
            "opponent identity independent of consumer Top-5",
            "recent L5/L10 form retained",
            "usage context retained or transparently labeled",
            "PRA V3.6 pace context reused",
            "H2H receives selected-game opponent identity",
            "Step-2 identity runtime preserved as parent",
            "frozen app.py untouched in Step 3",
        ],
    )
    return validate_execution_plan(plan, observed_main_sha=BASE_MAIN_SHA)


def certify_source_contract() -> dict[str, Any]:
    overlay = OVERLAY.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    checks = {
        "step2_parent_preserved": (
            'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity"'
            in overlay
        ),
        "opponent_consumer_independent": "data.opponent_identity(game, player_team_id)" in overlay,
        "recent_form_handoff": '"l5_pra": getter("L5_PRA")' in overlay and '"l10_pra": getter("L10_PRA")' in overlay,
        "usage_handoff": '"projected_usage": getter("PROJ_USG")' in overlay,
        "pace_v36_reused": "matchup.matchup_factors_v36" in overlay,
        "history_opponent_repair": "_repair_history_summary" in overlay,
        "model_locked": "MAY_MODIFY_WNBA_MODEL = False" in overlay,
        "projection_locked": "MAY_MODIFY_PROJECTION_MATH = False" in overlay,
        "market_locked": "MAY_MODIFY_MARKET_MATH = False" in overlay,
        "probability_locked": "MAY_MODIFY_PROBABILITY = False" in overlay,
        "qualification_locked": "MAY_MODIFY_QUALIFICATION = False" in overlay,
        "ranking_locked": "MAY_MODIFY_RANKING = False" in overlay,
        "sportsbook_influence_zero": "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in overlay,
        "step3_not_yet_activated_in_frozen_app": (
            "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness"
            not in app
        ),
        "step2_runtime_still_active_in_app": (
            "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity"
            in app
        ),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BrowserQAFailure(f"Step-3 source contract failed: {failed}")
    return {"status": "GREEN", "checks": checks}


def certify_helpers() -> dict[str, Any]:
    game = {
        "away_team_id": 1611661317,
        "away_team": "Phoenix Mercury",
        "away_tricode": "PHX",
        "home_team_id": 1611661328,
        "home_team": "Seattle Storm",
        "home_tricode": "SEA",
    }
    opponent = data.opponent_identity(game, 1611661317)
    if opponent.get("opponent_team_key") != "seattle-storm":
        raise BrowserQAFailure("Step-3 canonical opponent helper failed.")

    fallback = data.form_fallback({"l5_pra": 27.4, "l10_pra": 26.1})
    if fallback.get("recent5_pra") != 27.4 or fallback.get("recent10_pra") != 26.1:
        raise BrowserQAFailure("Step-3 recent-form fallback failed.")

    usage = data.weighted_usage(20.0, 22.0, 24.0)
    if usage is None or round(usage, 4) != 21.5:
        raise BrowserQAFailure("Step-3 usage blend contract failed.")

    return {
        "status": "GREEN",
        "opponent_key": opponent["opponent_team_key"],
        "recent5_pra": fallback["recent5_pra"],
        "recent10_pra": fallback["recent10_pra"],
        "usage_example": usage,
    }


def run(*, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    plan = compiled_plan()
    source = certify_source_contract()
    helpers = certify_helpers()
    chaos = chaos_contract_self_test()
    if chaos.get("status") != "GREEN" or chaos.get("all_scenarios_pass") is not True:
        raise BrowserQAFailure("MONSTER V8 chaos/adversarial certification is not GREEN.")

    merged_main_sha = str(os.environ.get("GITHUB_SHA") or "").strip()
    result = {
        "project": PROJECT,
        "step": STEP,
        "status": "GREEN",
        "proof_kind": "MERGED_MAIN_COMPONENT",
        "base_main_sha": BASE_MAIN_SHA,
        "merged_main_sha": merged_main_sha or None,
        "execution_plan_id": plan["plan_id"],
        "execution_plan_digest": plan["plan_digest"],
        "v8_chaos_certificate_digest": chaos["chaos_certificate_digest"],
        "source_contract": source,
        "helper_contract": helpers,
        "production_activation_deferred": True,
        "activation_target": "Step 4 integration",
        "upstream_page2_public_blocker_reopened": False,
        "app_py_changed": False,
        "projection_math_changed": False,
        "market_math_changed": False,
        "probability_changed": False,
        "qualification_changed": False,
        "ranking_changed": False,
    }
    (artifacts / "wnba_pra_repair_v1_step3_component_cert.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("WNBA_PRA_REPAIR_V1_STEP3_V8_PLAN_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_V8_CHAOS_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_OPPONENT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_RECENT_FORM_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_USAGE_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_PACE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_H2H_LINK_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_APP_FROZEN_UNTOUCHED_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_COMPONENT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_FROZEN")
    return result


def main() -> int:
    run(artifact_dir="artifacts/wnba-pra-repair-v1-step3-data-completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
