from __future__ import annotations

from pathlib import Path

import cfb_game_total_step6_scoring_v1 as frozen
import cfb_game_total_step6_visual_v2 as visual


PAGE = Path("cfb_game_total_clean_page_v19.py")
ROUTER = Path("streamlit_memory_lazy_router_v164.py")
APP = Path("app.py")


def _identity():
    return {
        "away": {
            "team": "North Carolina",
            "team_id": "153",
            "logo": "https://example.test/unc.png",
            "conference": "ACC",
        },
        "home": {
            "team": "Clemson",
            "team_id": "228",
            "logo": "https://example.test/clemson.png",
            "conference": "ACC",
        },
    }


def _metrics(pass_rate, rush_rate, overall_rate, ops, conversion, rz_td, *, defense=False):
    row = {
        "games": 4,
        "pass_explosive_rate": pass_rate,
        "rush_explosive_rate": rush_rate,
        "overall_explosive_rate": overall_rate,
        "scoring_ops_pg": ops,
        "scoring_op_conversion": conversion,
        "red_zone_td_rate": rz_td,
        "coverage": 1.0,
        "source": "SportsDataverse current-season completed-game PBP",
    }
    if defense:
        row["big_play_susceptibility"] = overall_rate
        row["red_zone_td_rate_allowed"] = rz_td
        row["scoring_op_conversion_allowed"] = conversion
    return row


def _evidence():
    return {
        "away_offense": _metrics(0.18, 0.22, 0.19, 5.7, 0.78, 0.68),
        "away_defense": _metrics(0.12, 0.18, 0.14, 4.4, 0.64, 0.55, defense=True),
        "home_offense": _metrics(0.15, 0.17, 0.16, 4.8, 0.70, 0.61),
        "home_defense": _metrics(0.10, 0.14, 0.11, 3.8, 0.58, 0.48, defense=True),
        "away_event_ids": ["401000001", "401000002"],
        "home_event_ids": ["401000003", "401000004"],
        "unique_events_loaded": 4,
    }


def test_v185_visual_owner_consumes_frozen_contract_without_reimplementing_data():
    assert visual.build_step6_contract is frozen.build_step6_contract
    assert visual.FROZEN_DATA_OWNER == "cfb_game_total_step6_scoring_v1"
    assert visual.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert visual.MAY_MODIFY_PROJECTION is False


def test_v185_target_visual_contract_is_full_width_and_preserves_v184_dom():
    html = visual.render_step6_html(
        "READY",
        _identity(),
        {"team": "North Carolina", "record_text": "2-1"},
        {"team": "Clemson", "record_text": "3-0"},
        {
            "game_date": "2026-09-21",
            "kickoff_et": "7:30 PM ET",
            "venue": "Memorial Stadium",
            "broadcast": "ABC",
        },
        evidence=_evidence(),
    )
    assert 'data-testid="gt157-step-6"' in html
    assert 'data-step6-state="READY"' in html
    assert 'data-step6-coverage="100"' in html
    assert 'data-step6-ready-tiles="12"' in html
    assert visual.STEP6_VISUAL_PARITY_MARKER in html
    assert html.count('data-testid="gt184-step6-stat-tile"') == 12
    assert html.count('data-ready="true"') == 12
    assert html.count('data-testid="gt185-step6-defense-tile"') == 12
    assert "STEP 6 — SCORING CREATION" in html
    assert "SCORING CREATION" in html
    assert "SCORING PREVENTION" in html
    assert "SCORING ENVIRONMENT" in html
    assert "MATCHUP READ" in html
    assert "BIGGEST ACCELERATOR" in html
    assert "BIGGEST SUPPRESSOR" in html
    assert "O/U IMPACT" in html
    assert "DATA CONFIDENCE" in html
    assert "Big-play susceptibility" in html
    assert "Red-zone TD rate allowed" in html
    assert "SPORTSBOOK INFLUENCE 0.0%" in html
    assert "PROJECTION MUTATION OFF" in html
    assert "grid-column:1/-1!important" in html
    assert "gt185-s6-battlepair" in html
    assert "gt185-s6-panel offense" in html
    assert "gt185-s6-panel defense" in html


def test_v185_page_is_additive_over_frozen_v184_and_swaps_renderer_only():
    source = PAGE.read_text(encoding="utf-8")
    assert "import cfb_game_total_clean_page_v18 as prior_v184" in source
    assert "import cfb_game_total_step6_visual_v2 as step6_visual" in source
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v18"' in source
    assert "_VISUAL_RENDER_LOCK = RLock()" in source
    assert "with _VISUAL_RENDER_LOCK:" in source
    assert "prior_v184.step6_owner.render_step6_html = step6_visual.render_step6_html" in source
    assert "prior_v184.render_game_total_hub" in source
    assert "prior_v184.render_step6_cert_surface" in source
    assert "load_matchup_team_data" not in source
    assert "enrich_step3_inputs" not in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v185_router_advances_only_exact_game_total_to_page_v19():
    source = ROUTER.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v163 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v163"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v19"' in source
    assert "original_heartbeat = prior.PRODUCTION_HEARTBEAT" in source
    assert "prior.PRODUCTION_HEARTBEAT = PRODUCTION_HEARTBEAT" in source
    assert "prior.PRODUCTION_HEARTBEAT = original_heartbeat" in source
    assert "CFB_GAME_TOTAL_V185_STEP6_VISUAL_PARITY_ACTIVE" in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v185_app_boots_router_v164_while_retaining_v184_certification_string():
    source = APP.read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v164 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v163 import record_bootstrap_import_ms, render_app" in source
