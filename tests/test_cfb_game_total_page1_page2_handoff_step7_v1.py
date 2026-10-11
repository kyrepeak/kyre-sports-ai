from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/cfb_game_total_page1_page2_handoff_step7_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
V43 = ROOT / "cfb_game_total_clean_page_v43.py"
V14 = ROOT / "cfb_game_total_clean_page_v14.py"
V11 = ROOT / "cfb_game_total_clean_page_v11.py"
PAGE2 = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"
PLAN = ROOT / "devsystem/runless_proof_plans/cfb-game-total-page1-page2-handoff-step7-v1.json"


def _load_cert():
    import importlib.util

    assert CERT.exists(), "Step 7 handoff certification owner is not implemented yet"
    spec = importlib.util.spec_from_file_location("cfb_gt_step7_handoff_cert", CERT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step7_certification_owner_exists_and_is_non_mutating():
    module = _load_cert()
    assert module.MODEL_VERSION == "CFB GAME TOTAL • PAGE1 TO PAGE2 HANDOFF • STEP 7 V1"
    assert module.MAY_MODIFY_PAGE1 is False
    assert module.MAY_MODIFY_PAGE2 is False
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_MODIFY_OTHER_SPORTS is False
    assert module.NETWORK_CALLS_ADDED == 0
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_step7_certifies_exact_card_query_to_frozen_page2_runtime():
    module = _load_cert()
    result = module.certify_handoff_contract()
    assert result["status"] == "GREEN"
    assert result["page1_owner"] == "cfb_game_total_clean_page_v43"
    assert result["page2_runtime"] == "cfb_game_total_page2_step8_final_runtime_v1"
    assert result["event_query_key"] == "ks_cfb_game_total_event_id"
    assert result["selector_sync_query_key"] == "ks_cfb_game_total_selector_sync"
    assert result["date_query_key"] == "ks_cfb_game_total_date"
    assert result["selected_day"] == "2026-10-10"
    assert result["event_id"] == "401760001"
    assert result["handoff_query"] == {
        "ks_cfb_game_total_date": "2026-10-10",
        "ks_cfb_game_total_event_id": "401760001",
        "ks_cfb_game_total_selector_sync": "401760001",
        "ks_cfb_market": "Game Total",
        "ks_sport": "College Football",
    }
    assert result["page2_selected_event_activation"] is True
    assert result["router_observed_page2_owners"] == {
        "cfb": "cfb_game_total_page2_step8_final_runtime_v1",
        "live": "cfb_game_total_page2_step8_final_runtime_v1",
        "render": "cfb_game_total_page2_step8_final_runtime_v1",
    }
    assert result["router_restored_after_render"] is True
    assert result["phoenix_timezone"] == "America/Phoenix"


def test_step7_resolves_actual_v11_date_query_binding():
    module = _load_cert()
    source = V11.read_text(encoding="utf-8")
    assert module._resolve_v11_date_query_key(source) == "ks_cfb_game_total_date"
    alternate = source.replace(
        'DATE_QUERY_KEY = "ks_cfb_game_total_date"',
        'DATE_QUERY_KEY = "ks_cfb_game_total_date_v2"',
        1,
    )
    assert module._resolve_v11_date_query_key(alternate) == "ks_cfb_game_total_date_v2"


def test_step7_exercises_selected_event_router_runtime_path():
    module = _load_cert()
    result = module._exercise_selected_event_router()
    assert result["selected"] is True
    assert result["observed_page2_owners"] == {
        "cfb": "cfb_game_total_page2_step8_final_runtime_v1",
        "live": "cfb_game_total_page2_step8_final_runtime_v1",
        "render": "cfb_game_total_page2_step8_final_runtime_v1",
    }
    assert result["restored"] is True


def test_step7_preserves_frozen_step6_and_page2_contracts():
    router = ROUTER.read_text(encoding="utf-8")
    v43 = V43.read_text(encoding="utf-8")
    v14 = V14.read_text(encoding="utf-8")
    page2 = PAGE2.read_text(encoding="utf-8")

    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v43"' in router
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in router
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in router
    assert "if not _selected_game_total():" in router
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in router
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in router
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in router

    assert "MAY_MODIFY_PAGE2 = False" in v43
    assert 'SELECTOR_SYNC_QUERY_KEY = "ks_cfb_game_total_selector_sync"' in v14
    assert 'TIMEZONE = "America/Phoenix"' in page2
    assert "MAY_MODIFY_PAGE1 = False" in page2
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page2


def test_step7_runless_plan_is_integration_only_and_has_no_public_probe():
    assert PLAN.exists(), "Step 7 Runless proof plan is not implemented yet"
    text = PLAN.read_text(encoding="utf-8")
    assert '"tests/test_cfb_game_total_page1_page2_handoff_step7_v1.py"' in text
    assert '"probes": []' in text
    assert '"cfb_game_total_clean_page_v43.py"' in text
    assert '"cfb_game_total_clean_page_v11.py"' in text
    assert '"streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"' in text
    assert '"cfb_game_total_page2_step8_final_runtime_v1.py"' in text
