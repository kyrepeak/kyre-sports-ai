from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V43 = ROOT / "cfb_game_total_clean_page_v43.py"
V42 = ROOT / "cfb_game_total_clean_page_v42.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
PROOF_PLAN = ROOT / "devsystem/runless_proof_plans/cfb-game-total-game-cards-step6-v1.json"


def test_step6_adds_native_game_card_owner_without_reopening_step5_data():
    assert V43.exists(), "Step 6 must add V43 as the native game-card owner"
    source = V43.read_text()

    assert "import cfb_game_total_clean_page_v42 as prior" in source
    assert 'GAME_CARDS_MARKER = "CFB_GAME_TOTAL_GAME_CARDS_STEP6_ACTIVE"' in source
    assert "CARDS_CONSUME_SELECTED_DAY_SNAPSHOT = True" in source
    assert "FROZEN_CARD_PRESENTATION_REUSED = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "NEW_PROVIDER_PATHS_ADDED = 0" in source
    assert "return prior.render_game_total_hub(" in source

    assert "_load_games(" not in source
    assert "requests." not in source
    assert "load_with_diagnostics(" not in source


def test_step6_rebinds_entire_card_chain_after_clean_page_module_purge():
    source = V43.read_text()
    step2_import = "from cfb_game_total_games_on_day_step2_visual_v1 import install_games_on_day_step2_visual"
    step3_import = "from cfb_game_total_games_on_day_step3_details_v1 import install_games_on_day_step3_details"
    step4_import = "from cfb_game_total_games_on_day_step4_interaction_mobile_v1 import install_games_on_day_step4_interaction_mobile"
    assert step2_import in source
    assert step3_import in source
    assert step4_import in source
    assert "POST_PURGE_CARD_REBIND = True" in source

    step2_call = source.index("install_games_on_day_step2_visual()")
    step3_call = source.index("install_games_on_day_step3_details()")
    step4_call = source.index("install_games_on_day_step4_interaction_mobile()")
    render_call = source.index("return prior.render_game_total_hub(")
    assert step2_call < step3_call < step4_call < render_call


def test_step6_promotes_existing_frozen_game_card_chain_only_on_page1():
    router = ROUTER.read_text()
    v42 = V42.read_text()

    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v43"' in router
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in router
    assert router.count("install_games_on_day_step2_visual()") == 1
    assert router.count("install_games_on_day_step3_details()") == 1
    assert router.count("install_games_on_day_step4_interaction_mobile()") == 1
    assert "if not _selected_game_total():" in router

    assert "SELECTED_DAY_SNAPSHOT_OWNS_GAME_LOADING = True" in v42
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v42"' in V43.read_text()


def test_step6_runless_plan_uses_forward_compatible_preservation_proof():
    plan = PROOF_PLAN.read_text()
    assert '"tests/test_cfb_game_total_game_cards_step6_v1.py"' in plan
    assert '"tests/test_cfb_game_total_games_on_day_data_step5_v1.py"' not in plan
    assert '"tests/test_devsystem_cfb_game_total_backend_preservation_step2_v1.py"' in plan
