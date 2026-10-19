from __future__ import annotations

import importlib
import importlib.util


def _module():
    spec = importlib.util.find_spec("nba_spread_page2_selected_game_v1")
    assert spec is not None, "nba_spread_page2_selected_game_v1 must exist"
    return importlib.import_module("nba_spread_page2_selected_game_v1")


def test_selected_game_detail_is_presentation_only_and_exact_identity():
    mod = _module()
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mod.MAY_MODIFY_MODEL is False
    assert mod.MAY_MODIFY_PROJECTION is False
    assert mod.MAY_MODIFY_PROBABILITY is False
    assert mod.MAY_MODIFY_RANKING is False

    state = {
        "verification": "VERIFIED",
        "game": {
            "game_key": "BOS@DET:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": "BOS",
            "home_tricode": "DET",
            "away_name": "Boston Celtics",
            "home_name": "Detroit Pistons",
            "tip_phoenix": "12:00 PM MST",
            "venue": "Little Caesars Arena",
        },
        "fair_record": {
            "verification": "VERIFIED",
            "pregame_model": {
                "verification": "VERIFIED",
                "fair_away_spread": -3.0,
                "fair_home_spread": 3.0,
                "cover_verification": "VERIFIED",
                "away_cover_probability": 0.578,
                "home_cover_probability": 0.422,
            },
        },
        "decision_record": {
            "verification": "VERIFIED",
            "decision_state": "PLAY",
            "pick_text": "BOS -1.5",
            "pick_strength": "LEAN",
            "production_grade": "C",
        },
    }
    html = mod._selected_game_html(state, market={"verification": "VERIFIED", "away_spread": -1.5, "home_spread": 1.5, "label": "2 books verified"}, injuries={"away_summary": "BOS: clear", "home_summary": "DET: 1 Q"})
    for expected in ("BOS @ DET", "Little Caesars Arena", "Kyre Fair Spread", "BOS -3", "57.8%", "BOS -1.5", "2 books verified", "DET: 1 Q"):
        assert expected in html
    assert "SPORTSGAMEODDS_" not in html


def test_unavailable_selected_game_renders_fail_closed_message():
    mod = _module()
    html = mod._selected_game_html({"verification": "UNAVAILABLE", "diagnostic_state": "SELECTED_GAME_NOT_FOUND"}, market={}, injuries={})
    assert "Selected game is unavailable" in html
    assert "SELECTED_GAME_NOT_FOUND" not in html
