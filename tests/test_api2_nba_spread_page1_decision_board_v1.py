from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.find_spec("nba_spread_page_v8")
    assert spec is not None, "nba_spread_page_v8 must exist"
    return importlib.import_module("nba_spread_page_v8")


def test_v8_is_additive_over_v7_and_preserves_frozen_model_ownership():
    mod = _module()
    assert mod.FROZEN_PARENT_PAGE == "nba_spread_page_v7"
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mod.MAY_MODIFY_MODEL is False
    assert mod.MAY_MODIFY_PROJECTION is False
    assert mod.MAY_MODIFY_PROBABILITY is False
    assert mod.MAY_MODIFY_RANKING is False
    assert mod.MAY_MODIFY_PAGE2 is False


def test_human_slate_label_is_readable_not_iso_only():
    mod = _module()
    assert mod._human_slate_label("2026-10-20") == "NEXT NBA SLATE • TUE OCT 20"


def test_decision_card_html_contains_launch_fields_and_explicit_analysis_target():
    mod = _module()
    record = {
        "game_key": "BOS@DET:2026-10-20",
        "date": "2026-10-20",
        "away_tricode": "BOS",
        "home_tricode": "DET",
        "away_name": "Boston Celtics",
        "home_name": "Detroit Pistons",
        "tip_phoenix": "4:00 PM MST",
        "venue": "Little Caesars Arena",
        "away_logo": None,
        "home_logo": None,
        "market": {"coverage": "CONSENSUS", "away_spread": -1.5, "home_spread": 1.5, "sportsbook_count": 3, "label": "3 books verified"},
        "fair": {"verification": "VERIFIED", "away_spread": -3.0, "home_spread": 3.0},
        "cover": {"verification": "VERIFIED", "away_probability": 0.578, "home_probability": 0.422},
        "edge_points": 1.5,
        "injuries": {"away_summary": "BOS: 1 OUT", "home_summary": "DET: 2 OUT • 2 Q"},
        "decision": {"verification": "VERIFIED", "decision_state": "PLAY", "pick_text": "BOS -1.5", "pick_strength": "LEAN", "production_grade": "C"},
        "line_movement": {"label": "First seen -2 → Current -1.5"},
        "public_betting": None,
    }
    html = mod._decision_card_html(record)
    for expected in (
        "BOS @ DET", "Market", "Kyre Fair Spread", "Cover Probability", "Edge",
        "BOS: 1 OUT", "DET: 2 OUT • 2 Q", "BOS -1.5", "First seen -2 → Current -1.5",
        "View Analysis →",
    ):
        assert expected in html
    assert "3 books verified" in html


def test_fair_value_stays_visible_when_market_is_unavailable():
    mod = _module()
    record = {
        "game_key": "BOS@DET:2026-10-20",
        "date": "2026-10-20",
        "away_tricode": "BOS",
        "home_tricode": "DET",
        "away_name": "Boston Celtics",
        "home_name": "Detroit Pistons",
        "tip_phoenix": "4:00 PM MST",
        "venue": "Arena",
        "away_logo": None,
        "home_logo": None,
        "market": {"coverage": "UNAVAILABLE", "label": "Market verification pending"},
        "fair": {"verification": "VERIFIED", "away_spread": -3.0, "home_spread": 3.0},
        "cover": {"verification": "UNAVAILABLE"},
        "edge_points": None,
        "injuries": {"away_summary": "BOS: clear", "home_summary": "DET: clear"},
        "decision": {"verification": "UNAVAILABLE", "decision_state": "NO_PLAY", "consumer_reason": "Market verification pending"},
        "line_movement": None,
        "public_betting": None,
    }
    html = mod._decision_card_html(record)
    assert "BOS -3" in html
    assert "Market verification pending" in html
    assert "STEP9_" not in html and "SPORTSGAMEODDS_" not in html


def test_page_source_keeps_diagnostics_collapsed_and_mobile_layout_dense():
    page = ROOT / "nba_spread_page_v8.py"
    assert page.exists(), "nba_spread_page_v8 must exist"
    source = page.read_text(encoding="utf-8")
    assert 'st.expander("Sources & Diagnostics", expanded=False)' in source
    assert "View Analysis" in source
    assert "@media(max-width:600px)" in source or "@media (max-width:600px)" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
