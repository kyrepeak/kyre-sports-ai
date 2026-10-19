from __future__ import annotations

import importlib
from pathlib import Path


def test_v5_module_preserves_frozen_model_contract():
    v4 = importlib.import_module("cfb_moneyline_clean_page_v4")
    v5 = importlib.import_module("cfb_moneyline_clean_page_v5")
    assert v5.FROZEN_MONEYLINE_OWNER == v4.FROZEN_MONEYLINE_OWNER
    assert v5.FROZEN_RAW_MODEL == v4.FROZEN_RAW_MODEL
    assert v5.FROZEN_FINAL_MODEL == v4.FROZEN_FINAL_MODEL
    assert v5.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v5.MAY_MODIFY_PROJECTION is False


def test_team_profile_panel_is_professional_card_layout():
    v5 = importlib.import_module("cfb_moneyline_clean_page_v5")
    away = {
        "team": "Middle Tenn.", "record": "2-4", "rank": None, "sample_size": 6,
        "points_per_game": 22.8, "points_allowed_per_game": 28.3, "point_diff_per_game": -5.5,
        "total_offense": 321.5, "total_defense": 415.7, "turnover_margin": 0.67,
        "home_record": "0-0", "away_record": "0-0", "neutral_record": "0-0",
    }
    home = {
        "team": "FIU", "record": "3-3", "rank": None, "sample_size": 6,
        "points_per_game": 19.7, "points_allowed_per_game": 14.7, "point_diff_per_game": 5.0,
        "total_offense": 300.0, "total_defense": 350.0, "turnover_margin": 0.33,
        "home_record": "0-0", "away_record": "0-0", "neutral_record": "0-0",
    }
    html = v5._team_profiles_html(away, home, visuals={"away": {"logo": "away.png"}, "home": {"logo": "home.png"}})
    assert "cfbm5-team-grid" in html
    assert "Middle Tenn." in html and "FIU" in html
    assert "away.png" in html and "home.png" in html
    assert "Points / game" in html
    assert "Allowed / game" in html
    assert "Point differential" in html
    assert "Total offense" in html
    assert "Total defense" in html
    assert "Turnover margin" in html
    assert "Data quality" in html


def test_model_dashboard_is_scannable_and_keeps_raw_debug_out_of_primary_surface():
    v5 = importlib.import_module("cfb_moneyline_clean_page_v5")
    raw = {
        "ready": True, "away_probability": 0.442, "home_probability": 0.558,
        "away_projected_score": 21.6, "home_projected_score": 24.0,
        "home_margin": 2.5, "projected_total": 45.6, "confidence": "MEDIUM",
        "reliability": 0.938, "feature_coverage": 0.75,
    }
    final = {
        "ready": True, "winner_team": "FIU", "winner_probability_final": 0.551,
        "away_probability_final": 0.449, "home_probability_final": 0.551,
        "away_fair_moneyline": 123, "home_fair_moneyline": -123,
        "away_projected_score": 21.6, "home_projected_score": 24.0,
        "home_margin": 2.5, "reliability": 0.938, "feature_coverage": 0.75,
        "model_grade": "C LEAN", "calibration_temperature": 1.15,
        "home_probability_structural_90": [0.461, 0.640],
        "margin_structural_90": [-19.0, 23.9],
    }
    html = v5._model_dashboard_html(raw, final, away_name="Middle Tenn.", home_name="FIU")
    assert "cfbm5-model-grid" in html
    assert "Final model pick" in html
    assert "FIU" in html
    assert "55.1%" in html
    assert "-123" in html
    assert "Projected score" in html
    assert "Reliability" in html
    assert "Feature coverage" in html
    assert "Model uncertainty" in html
    assert "PRE-CALIBRATION" not in html
    assert "STEP 5" not in html


def test_v5_source_uses_clean_primary_sections_and_advanced_transparency_expanders():
    source = Path("cfb_moneyline_clean_page_v5.py").read_text()
    assert 'st.expander("🏟️ Team profiles & availability"' in source
    assert 'st.expander("🧠 Model details"' in source
    assert 'st.expander("🔎 Data source details"' in source
    assert 'st.expander("⚙️ Advanced model details"' in source
    assert "_team_profiles_html" in source
    assert "_model_dashboard_html" in source


def test_loader_v17_routes_only_cfb_moneyline_to_v5_and_router_advances():
    loader = Path("universal_runtime_v5_loader_v17.py").read_text()
    router = Path("streamlit_memory_lazy_router_universal_runtime_v5.py").read_text()
    assert "import universal_runtime_v5_loader_v16 as prior" in loader
    assert 'page = importlib.import_module("cfb_moneyline_clean_page_v5")' in loader
    assert 'route.sport_id == "cfb" and route.market_id == "moneyline"' in loader
    assert "from universal_runtime_v5_loader_v17 import choose_prefetch, load_destination, resolve_destination" in router
