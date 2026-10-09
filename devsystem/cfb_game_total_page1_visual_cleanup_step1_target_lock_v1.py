from __future__ import annotations

import json

TASK_ID = "cfb-game-total-page1-visual-cleanup-step1-target-lock"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
STEP = "1/5"
SOURCE_MAIN_SHA = "1eb550e58964ace5f9551a484d1c65cd49f8fc20"
TIMEZONE = "America/Phoenix"

TARGET_SECTION_ORDER = (
    "MATCHUP_HERO",
    "GAME_CONTEXT_STRIP",
    "OVERVIEW_FULL_ANALYSIS_TABS",
    "GAME_PREDICTION_AND_MARKET_COMPARISON",
    "FAVORABLE_KEY_EDGE_TOUGHNESS",
    "TEAM_SNAPSHOT",
    "GAMES_ON_THIS_DAY",
    "SOURCES_UPDATED_HOW_WE_CALCULATE",
)

OVERVIEW_EXCLUDES_PRIMARY_BLOCKS = (
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)

FULL_ANALYSIS_SECONDARY_EVIDENCE = (
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)

REFERENCE_MATCHUP_IS_ILLUSTRATIVE = True
MAY_HARDCODE_REFERENCE_VALUES = False
PRESERVE_DYNAMIC_SELECTED_GAME_DATA = True
MOCKUP_TIME_LABELS_ARE_ILLUSTRATIVE = True

PRODUCT_RUNTIME_MUTATIONS = 0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
GITHUB_ACTIONS_FALLBACK = 0

ACTIVE_PAGE_OWNER = "cfb_game_total_clean_page_v38"
PUBLIC_REPAIR = "cfb_game_total_page1_v2_step4_public_repair_v1"
ROUTER_CHAIN = (
    "streamlit_memory_lazy_router_v160",
    "streamlit_memory_lazy_router_v181",
    "streamlit_memory_lazy_router_v190",
    "streamlit_memory_lazy_router_v191",
)

PRIOR_VISUAL_CONTRACT = "docs/CFB_GAME_TOTAL_VISUAL_REDESIGN_V1_CONTRACT.md"
SUPERSEDES_PRIOR_HIERARCHY_ONLY = True
PRESERVES_PRIOR_ACCESSIBILITY_AND_VISUAL_TOKENS = True
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP1_TARGET_LOCK_FROZEN"


def execute() -> dict[str, object]:
    return {
        "status": "GREEN",
        "decision": "CFB_GAME_TOTAL_PAGE1_VISUAL_TARGET_LOCKED",
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "step": STEP,
        "source_main_sha": SOURCE_MAIN_SHA,
        "timezone": TIMEZONE,
        "target_section_order": list(TARGET_SECTION_ORDER),
        "overview_primary_exclusions": list(OVERVIEW_EXCLUDES_PRIMARY_BLOCKS),
        "full_analysis_secondary_evidence": list(FULL_ANALYSIS_SECONDARY_EVIDENCE),
        "reference_matchup_is_illustrative": REFERENCE_MATCHUP_IS_ILLUSTRATIVE,
        "preserve_dynamic_selected_game_data": PRESERVE_DYNAMIC_SELECTED_GAME_DATA,
        "product_runtime_mutations": PRODUCT_RUNTIME_MUTATIONS,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        "freeze_token": FREEZE_TOKEN,
    }


def main() -> int:
    print("CFB_GT_PAGE1_VISUAL_CLEANUP_STEP1=" + json.dumps(execute(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
