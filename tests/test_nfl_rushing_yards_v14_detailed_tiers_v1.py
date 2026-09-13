from pathlib import Path

import nfl_rushing_yards_hub_v13 as frozen_v13
import nfl_rushing_yards_hub_v14 as page
import streamlit_memory_lazy_router_v109 as frozen_router
import streamlit_memory_lazy_router_v110 as router


def _team(team_id: str, opponent_id: str, abbr: str, run_front: dict | None = None):
    row = {
        "official_team_id": team_id,
        "opponent_official_team_id": opponent_id,
        "team_abbreviation": abbr,
    }
    if run_front is not None:
        row["opponent_run_front"] = run_front
    return row


def _proj(athlete_id: str, team_id: str, opponent_id: str):
    return {
        "ready": True,
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "opponent_official_team_id": opponent_id,
        "player_name": athlete_id,
    }


def test_v14_is_display_only_over_frozen_v13():
    assert page.FROZEN_PRIOR == "nfl_rushing_yards_hub_v13"
    assert page.DISPLAY_ONLY is True
    assert page.MATCHUP_CLASSIFICATION_ONLY is True
    assert page.BETTING_GRADE_ENABLED is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert frozen_v13.FROZEN_PRIOR == "nfl_rushing_yards_hub_v12"


def test_sort_places_favorable_then_medium_then_tough(monkeypatch):
    result = {
        "ready": True,
        "projections": [
            _proj("tough", "1", "2"),
            _proj("medium", "3", "4"),
            _proj("favorable", "5", "6"),
        ],
    }
    context = {
        "teams": [
            _team("1", "2", "A"), _team("2", "1", "B"),
            _team("3", "4", "C"), _team("4", "3", "D"),
            _team("5", "6", "E"), _team("6", "5", "F"),
        ]
    }
    tiers = {"1": "TOUGH", "3": "MEDIUM", "5": "FAVORABLE"}
    monkeypatch.setattr(
        page,
        "_grade_for_team_opponent",
        lambda team, opponent: {"tier": tiers[team["official_team_id"]], "score": 0},
    )
    sorted_result = page._sorted_projection_result(result, context)
    assert [r["official_athlete_id"] for r in sorted_result["projections"]] == [
        "favorable", "medium", "tough"
    ]


def test_sort_is_stable_inside_same_tier(monkeypatch):
    result = {
        "ready": True,
        "projections": [
            _proj("a", "1", "2"),
            _proj("b", "3", "4"),
            _proj("c", "5", "6"),
        ],
    }
    context = {"teams": [
        _team("1", "2", "A"), _team("2", "1", "B"),
        _team("3", "4", "C"), _team("4", "3", "D"),
        _team("5", "6", "E"), _team("6", "5", "F"),
    ]}
    monkeypatch.setattr(page, "_grade_for_team_opponent", lambda team, opponent: {"tier": "MEDIUM", "score": 0})
    sorted_result = page._sorted_projection_result(result, context)
    assert [r["official_athlete_id"] for r in sorted_result["projections"]] == ["a", "b", "c"]


def test_detailed_stack_gets_visible_tier_ribbon(monkeypatch):
    monkeypatch.setattr(
        page,
        "_ORIGINAL_FINAL_CARD_V9",
        lambda projection_row, team, opponent, market_row: '<div class="original-stack">STACK</div>',
    )
    monkeypatch.setattr(
        page,
        "_grade_for_team_opponent",
        lambda team, opponent: {
            "tier": "FAVORABLE",
            "score": 3,
            "available": True,
            "favorable_signals": 3,
            "tough_signals": 0,
        },
    )
    html = page._detailed_player_card_v14(
        {"official_athlete_id": "4362238"},
        {"team_abbreviation": "CIN"},
        {"team_abbreviation": "TB"},
        {},
    )
    assert 'data-athlete-id="4362238"' in html
    assert 'data-matchup-tier="FAVORABLE"' in html
    assert 'data-detailed-matchup-score="+3"' in html
    assert "FAVORABLE" in html
    assert "vs TB" in html
    assert "STACK" in html


def test_v14_patches_and_restores_only_display_functions():
    source = Path("nfl_rushing_yards_hub_v14.py").read_text()
    assert "compact_page._compact_board_html = _compact_board_html_v14" in source
    assert "final_page._compact_player_card_v9 = _detailed_player_card_v14" in source
    assert "finally:" in source
    assert "compact_page._compact_board_html = original_board" in source
    assert "final_page._compact_player_card_v9 = original_final_card" in source
    for forbidden in (
        "build_player_projection(", "market_for_athlete(", "probability_enabled = True",
        "grading_enabled = True", "wager_actions = True", "stake_size", "kelly",
    ):
        assert forbidden not in source


def test_router_v110_advances_only_rushing_page():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v109"
    assert router.ACTIVE_PAGE == "nfl_rushing_yards_hub_v14"
    assert router.RUSHING_YARDS_MARKET == frozen_router.RUSHING_YARDS_MARKET == "Rushing Yards"


def test_app_activates_v110_and_preserves_v109_heartbeat():
    source = Path("app.py").read_text()
    assert "streamlit_memory_lazy_router_v110 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V109_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V109_NFL_RUSHING_YARDS_MATCHUP_TIERS_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V110_NFL_RUSHING_YARDS_DETAILED_MATCHUP_TIERS_2026-09-13"' in source
