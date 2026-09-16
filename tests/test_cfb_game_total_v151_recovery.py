from __future__ import annotations

from pathlib import Path

import cfb_game_total_monster_page_v2 as page
import streamlit_memory_lazy_router_v151 as router


def test_v151_routes_only_to_recovery_page_and_keeps_sportsbook_out():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v150"
    assert router.ACTIVE_PAGE == "cfb_game_total_monster_page_v2"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_unreconciled_zero_zero_is_not_presented_as_a_real_record():
    assert page._record({"record_text": "0-0"}, "PARTIAL") == "Record unavailable"
    assert page._record({"record_text": "0-0"}, "CHECK") == "Record unavailable"
    assert page._record({"record_text": "1-1"}, "PARTIAL") == "1-1"


def test_runtime_profile_ids_are_promoted_for_exact_logo_resolution():
    game = {"away_team": "Syracuse", "home_team": "Pittsburgh"}
    enriched = page._runtime_game_with_ids(
        game,
        {"espn_team_id": "183"},
        {"espn_team_id": "221"},
    )
    assert enriched["away_espn_team_id"] == "183"
    assert enriched["home_espn_team_id"] == "221"


def test_live_entrypoint_is_v151_not_v149():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v151 import record_bootstrap_import_ms, render_app" in text
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V151_CFB_GAME_TOTAL_LIVE_RECOVERY_2026-09-16"' in text


def test_page_uses_current_runtime_team_data_for_frozen_slate_handoff():
    source = Path("cfb_game_total_monster_page_v2.py").read_text(encoding="utf-8")
    assert "frozen_page.slate.team_data = runtime_data" in source
    assert "schedule_v5.load_with_diagnostics" in source
    assert "runtime_data.reconcile_runtime" in source
    assert "Open team evidence" in source
    assert "Open model evidence" in source
    assert "Open data-source diagnostics" in source
