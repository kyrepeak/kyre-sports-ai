from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cfb_game_total_page1_visual_cleanup_step4_footer_evidence_v1 import (
    MAY_MODIFY_OTHER_SPORTS,
    MAY_MODIFY_PROJECTION,
    NETWORK_CALLS_ADDED,
    PHOENIX_TZ,
    SPORTSBOOK_PROJECTION_INFLUENCE,
    build_footer_html,
    build_games_on_day_html,
    build_relocated_analysis_html,
)

ROOT = Path(__file__).resolve().parents[1]


def test_overview_relocates_dense_evidence_wall() -> None:
    html = build_relocated_analysis_html({}, {}, {}, {}, {}, {}, {}, {})
    assert 'data-testid="gtvc4-analysis-relocated"' in html
    assert "FULL ANALYSIS" in html
    assert "GAME TOTAL EVIDENCE • STEPS 1–12" not in html
    assert "FINAL MODEL SUMMARY" not in html
    assert "TOP-5 SLATE SCANNER" not in html


def test_games_on_day_is_dynamic_and_phoenix_time() -> None:
    games = [
        {
            "event_id": "401000001",
            "away_team": "Arizona",
            "home_team": "Utah",
            "start_time": "2026-10-10T23:30:00Z",
            "venue": "Rice-Eccles Stadium",
        },
        {
            "event_id": "401000002",
            "away": {"name": "Oklahoma"},
            "home": {"name": "Texas"},
            "date": "2026-10-10T16:00:00Z",
        },
    ]
    html = build_games_on_day_html(games, "2026-10-10")
    assert 'data-testid="gtvc4-games-on-day"' in html
    assert "Arizona" in html and "Utah" in html
    assert "Oklahoma" in html and "Texas" in html
    assert "PHX" in html
    assert "401000001" in html


def test_footer_has_sources_update_and_calculation_contract() -> None:
    now = datetime(2026, 10, 9, 9, 15, tzinfo=ZoneInfo(PHOENIX_TZ))
    html = build_footer_html(now=now)
    assert 'data-testid="gtvc4-data-footer"' in html
    assert "DATA SOURCES" in html
    assert "Kyre Sports API" in html
    assert "ESPN" in html
    assert "FanDuel" in html
    assert "UPDATED" in html
    assert "HOW WE CALCULATE" in html
    assert "0.0%" in html
    assert "9:15 AM PHX" in html


def test_step4_presentation_invariants() -> None:
    assert PHOENIX_TZ == "America/Phoenix"
    assert SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_OTHER_SPORTS is False
    assert NETWORK_CALLS_ADDED == 0


def test_activation_is_exact_route_post_purge_and_restores_hooks() -> None:
    source = (ROOT / "cfb_game_total_page1_visual_cleanup_step4_activation_v1.py").read_text(encoding="utf-8")
    assert 'TARGET_PAGE = "cfb_game_total_clean_page_v38"' in source
    assert 'importlib.import_module("cfb_game_total_clean_page_v9")' in source
    assert 'importlib.import_module("cfb_game_total_clean_page_v14")' in source
    assert "_combined_flow_html" in source
    assert "_render_game_strip" in source
    assert "load_with_diagnostics" in source
    assert "render_cfb_hub" in source
    assert "_game_total_route_active()" in source
    assert "finally:" in source


def test_frozen_side_market_seam_chains_step4_after_step3() -> None:
    source = (ROOT / "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py").read_text(encoding="utf-8")
    assert "install_step3_overview" in source
    assert "install_step4_footer_evidence" in source
    assert source.count("install_step4_footer_evidence()") >= 2


def test_step4_does_not_edit_frozen_model_owners() -> None:
    activation = (ROOT / "cfb_game_total_page1_visual_cleanup_step4_activation_v1.py").read_text(encoding="utf-8")
    helper = (ROOT / "cfb_game_total_page1_visual_cleanup_step4_footer_evidence_v1.py").read_text(encoding="utf-8")
    combined = activation + helper
    assert "scan_slate(" not in combined
    assert "rank_slate(" not in combined
    assert "projected_combined_total =" not in combined
    assert "requests.get(" not in combined
