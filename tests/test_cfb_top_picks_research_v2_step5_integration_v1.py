from __future__ import annotations

import cfb_top_picks_details_v1 as details
import cfb_top_picks_page_v4 as page


def _research():
    return {
        "status": "READY",
        "projection_weight": 0.0,
        "reasoning": [
            "Scoring prevention: Away State allows 18.0 PPG; Home Tech allows 22.0 PPG.",
            "Pace: Away State 72.0 plays/game; Home Tech 68.0 plays/game.",
        ],
        "away": {
            "team": "Away State",
            "metrics": {
                "points_allowed_per_game": {"value": 18.0},
                "recent_points_allowed_avg": {"value": 17.0},
                "yards_per_play_allowed": {"value": 4.9},
                "pass_yards_allowed_per_game": {"value": 205.0},
                "rush_yards_allowed_per_game": {"value": 120.0},
                "red_zone_td_rate_allowed": {"value": 0.50},
                "plays_per_game": {"value": 72.0},
                "seconds_per_play": {"value": 25.0},
                "pace_index": {"value": 1.08, "label": "FAST"},
                "explosive_susceptibility_proxy": {
                    "value": -0.1,
                    "label": "ABOVE-AVG SUPPRESSION",
                },
            },
        },
        "home": {
            "team": "Home Tech",
            "metrics": {
                "points_allowed_per_game": {"value": 22.0},
                "recent_points_allowed_avg": {"value": 24.0},
                "yards_per_play_allowed": {"value": 5.5},
                "pass_yards_allowed_per_game": {"value": 230.0},
                "rush_yards_allowed_per_game": {"value": 145.0},
                "red_zone_td_rate_allowed": {"value": 0.65},
                "plays_per_game": {"value": 68.0},
                "seconds_per_play": {"value": 28.0},
                "pace_index": {"value": 0.99, "label": "BALANCED"},
                "explosive_susceptibility_proxy": {
                    "value": 0.12,
                    "label": "ABOVE-AVG VULNERABILITY",
                },
            },
        },
    }


def _row():
    return {
        "rank": 1,
        "event_id": "401234567",
        "away": "Away State",
        "away_abbr": "AWY",
        "home": "Home Tech",
        "home_abbr": "HME",
        "time": "Sat, 12:00 PM",
        "network": "ESPN",
        "market": "MONEYLINE",
        "pick": "Away State",
        "odds": "-145",
        "probability": 68,
        "probability_value": 0.68,
        "toughness": 3,
        "toughness_label": "Medium",
        "reliability": 0.82,
    }


def test_step5_panel_renders_only_in_expanded_detail():
    row = _row()
    collapsed = page._cards_html([row], "", None)
    assert "Defense + Pace Research" not in collapsed

    detail = {
        "why": "Why",
        "benefit": "Benefit",
        "event_id": "401234567",
        "meetings": 0,
        "history_rows": [],
        "defense_pace_research": _research(),
        "defense_pace_reasoning": _research()["reasoning"],
    }
    expanded = page._cards_html([row], "401234567", detail)
    assert "Defense + Pace Research" in expanded
    assert "cfb-top-picks-defense-pace-research-1" in expanded
    assert "Allowed / Game" in expanded
    assert "Plays / Game" in expanded
    assert "projection weight 0.0%" in expanded


def test_step5_page_keeps_frozen_step4_marker_and_adds_step5_marker():
    html = page._page_html([_row()], {"games_analyzed": 1}, "2026-10-03")
    assert page.PAGE_MARKER in html
    assert page.RESEARCH_STEP5_MARKER in html
    assert "CFB_TOP_PICKS_STEP4_DETAILS_ACTIVE" in html
    assert "CFB_TOP_PICKS_RESEARCH_V2_STEP5_DEFENSE_PACE_ACTIVE" in html


def test_step5_detail_payload_field_names_are_frozen():
    source = open("cfb_top_picks_details_v1.py", encoding="utf-8").read()
    assert "defense_pace_research.build_defense_pace_research(row, game, slate_day)" in source
    assert '"defense_pace_research_projection_weight"' in source
