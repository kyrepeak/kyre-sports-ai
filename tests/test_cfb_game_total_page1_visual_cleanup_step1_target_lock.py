from pathlib import Path
import importlib.util

CERT = Path("devsystem/cfb_game_total_page1_visual_cleanup_step1_target_lock_v1.py")


def _load_cert():
    assert CERT.is_file(), "Step-1 visual cleanup target-lock cert must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_visual_cleanup_step1", CERT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_target_section_order_matches_approved_mockup_hierarchy():
    cert = _load_cert()
    assert cert.TARGET_SECTION_ORDER == (
        "MATCHUP_HERO",
        "GAME_CONTEXT_STRIP",
        "OVERVIEW_FULL_ANALYSIS_TABS",
        "GAME_PREDICTION_AND_MARKET_COMPARISON",
        "FAVORABLE_KEY_EDGE_TOUGHNESS",
        "TEAM_SNAPSHOT",
        "GAMES_ON_THIS_DAY",
        "SOURCES_UPDATED_HOW_WE_CALCULATE",
    )


def test_overview_is_summary_first_not_evidence_wall_first():
    cert = _load_cert()
    assert "GAME TOTAL EVIDENCE • STEPS 1–12" in cert.OVERVIEW_EXCLUDES_PRIMARY_BLOCKS
    assert "FINAL MODEL SUMMARY" in cert.OVERVIEW_EXCLUDES_PRIMARY_BLOCKS
    assert "TOP-5 SLATE SCANNER" in cert.OVERVIEW_EXCLUDES_PRIMARY_BLOCKS
    assert "GAME TOTAL EVIDENCE • STEPS 1–12" in cert.FULL_ANALYSIS_SECONDARY_EVIDENCE


def test_reference_mockup_is_visual_only_not_hardcoded_data():
    cert = _load_cert()
    assert cert.REFERENCE_MATCHUP_IS_ILLUSTRATIVE is True
    assert cert.MAY_HARDCODE_REFERENCE_VALUES is False
    assert cert.PRESERVE_DYNAMIC_SELECTED_GAME_DATA is True


def test_existing_truth_contracts_remain_frozen():
    cert = _load_cert()
    assert cert.PRODUCT_RUNTIME_MUTATIONS == 0
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert cert.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_existing_page1_v2_time_policy_is_preserved():
    cert = _load_cert()
    assert cert.TIMEZONE == "America/Phoenix"
    assert cert.MOCKUP_TIME_LABELS_ARE_ILLUSTRATIVE is True


def test_active_runtime_dependencies_are_documented_not_mutated():
    cert = _load_cert()
    assert cert.ACTIVE_PAGE_OWNER == "cfb_game_total_clean_page_v38"
    assert cert.PUBLIC_REPAIR == "cfb_game_total_page1_v2_step4_public_repair_v1"
    assert cert.ROUTER_CHAIN == (
        "streamlit_memory_lazy_router_v160",
        "streamlit_memory_lazy_router_v181",
        "streamlit_memory_lazy_router_v190",
        "streamlit_memory_lazy_router_v191",
    )


def test_prior_visual_contract_is_superseded_only_for_hierarchy():
    cert = _load_cert()
    assert cert.PRIOR_VISUAL_CONTRACT == "docs/CFB_GAME_TOTAL_VISUAL_REDESIGN_V1_CONTRACT.md"
    assert cert.SUPERSEDES_PRIOR_HIERARCHY_ONLY is True
    assert cert.PRESERVES_PRIOR_ACCESSIBILITY_AND_VISUAL_TOKENS is True
