from __future__ import annotations

import importlib
import inspect
from pathlib import Path


def _game():
    return {
        "away_team": "Middle Tennessee",
        "home_team": "FIU",
        "kickoff_iso": "2026-10-20T23:00:00+00:00",
        "identity_verified": True,
        "date_matches_query": True,
    }


def _raw():
    return {
        "ready": True,
        "confidence": "HIGH",
        "neutral_site": False,
        "components": {
            "home_base_points": 31.2,
            "away_base_points": 24.5,
            "home_recent_adjustment": 1.8,
            "away_recent_adjustment": -0.4,
            "home_efficiency_adjustment": 1.2,
            "away_efficiency_adjustment": -0.3,
            "turnover_edge_home_points": 0.8,
            "sos_edge_home_points": -0.2,
            "home_field_points": 2.0,
            "away_qb_state": "VERIFIED",
            "home_qb_state": "VERIFIED",
        },
    }


def _final():
    return {
        "ready": True,
        "winner_side": "home",
        "winner_team": "FIU",
        "winner_probability_final": 0.641,
        "home_win_probability_final": 0.641,
        "away_win_probability_final": 0.359,
        "home_fair_moneyline": -179,
        "away_fair_moneyline": 179,
        "model_grade": "A",
        "model_tier": "STRONG",
        "reliability": 0.84,
        "feature_coverage": 0.92,
    }


def test_v2_preserves_frozen_moneyline_boundaries():
    page = importlib.import_module("cfb_moneyline_clean_page_v2")
    assert page.FROZEN_MONEYLINE_OWNER == "cfb_moneyline_hub_v5"
    assert page.FROZEN_RAW_MODEL == "cfb_moneyline_model_v1"
    assert page.FROZEN_FINAL_MODEL == "cfb_moneyline_final_v1"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_decision_card_is_decision_first_and_human_facing():
    page = importlib.import_module("cfb_moneyline_clean_page_v2")
    html = page._decision_card(_game(), _raw(), _final())
    assert "MONEYLINE DECISION" in html
    assert "FIU" in html
    assert "64.1%" in html
    assert "Fair moneyline" in html
    assert "-179" in html
    assert "STRONG" in html
    assert "Step-5" not in html and "Step-6" not in html


def test_fail_closed_result_is_presented_as_pass_not_fake_pick():
    page = importlib.import_module("cfb_moneyline_clean_page_v2")
    html = page._decision_card(_game(), {}, {"ready": False, "reasons": ["insufficient verified inputs"]})
    assert "PASS" in html
    assert "NO QUALIFIED MODEL PICK" in html
    assert "insufficient verified inputs" in html
    assert "100.0%" not in html


def test_why_card_uses_football_language_and_explains_pick():
    page = importlib.import_module("cfb_moneyline_clean_page_v2")
    html = page._why_this_pick(_raw(), _final())
    for label in ("WHY THIS PICK", "Scoring profile", "Recent form", "Efficiency", "Turnovers", "Schedule strength", "Home field"):
        assert label in html
    assert "Step 5" not in html and "Step 6" not in html


def test_market_strip_is_display_only_and_never_invents_prices():
    page = importlib.import_module("cfb_moneyline_clean_page_v2")
    empty = page._market_price_strip(_game(), _final())
    assert "MARKET CHECK" in empty
    assert "No verified sportsbook moneyline is attached" in empty
    priced = dict(_game())
    priced["sportsbook_moneylines"] = {
        "FanDuel": {"home": -170, "away": 145, "updated_at": "2026-10-18T23:30:00Z"},
        "DraftKings": {"home": -165, "away": 140, "updated_at": "2026-10-18T23:31:00Z"},
    }
    html = page._market_price_strip(priced, _final())
    assert "FanDuel" in html and "DraftKings" in html
    assert "DISPLAY ONLY" in html
    assert "0% model weight" in html


def test_customer_page_hides_engineering_clutter_and_uses_football_sections():
    page = importlib.import_module("cfb_moneyline_clean_page_v2")
    source = inspect.getsource(page.render_moneyline_hub)
    assert "server render" not in source.lower()
    assert "prewarm" not in source.lower()
    assert "runtime data GREEN" not in source
    assert "FROZEN STEP-6 MODEL" not in source
    for label in ("Matchup & team profiles", "Model details", "Full verified slate"):
        assert label in source


def test_v14_routes_only_cfb_moneyline_to_v2():
    source = Path("universal_runtime_v5_loader_v14.py").read_text(encoding="utf-8")
    assert "import universal_runtime_v5_loader_v13 as prior" in source
    assert 'route.sport_id == "cfb" and route.market_id == "moneyline"' in source
    assert "cfb_moneyline_clean_page_v2" in source
    assert "return prior.resolve_destination(route)" in source


def test_runtime_v5_hands_off_to_loader_v14():
    source = Path("streamlit_memory_lazy_router_universal_runtime_v5.py").read_text(encoding="utf-8")
    assert "from universal_runtime_v5_loader_v14 import choose_prefetch, load_destination, resolve_destination" in source


def test_v14_preserves_universal_cfb_tap_only_and_next_slate_wrappers():
    source = Path("universal_runtime_v5_loader_v14.py").read_text(encoding="utf-8")
    assert "install_universal_tap_only_selectboxes" in source
    assert "resolve_runtime_cfb_slate_date" in source
    assert "install_cfb_next_slate_date_bridge" in source
    assert "SESSION_DATE_KEY" in source
