"""Regression checks for College Football Step 9 Over/Under Hub V3."""
from __future__ import annotations

import inspect

import cfb_over_under_hub_v3 as hub


def _game():
    return {
        "identity_key": "ncaa:123",
        "away_team": "Oklahoma",
        "home_team": "Michigan",
        "kickoff_et": "7:30 PM ET",
    }


def _final(selection="OVER", eligible=True):
    return {
        "ready": True,
        "selection": selection,
        "candidate_side": "OVER" if selection != "UNDER" else "UNDER",
        "selection_ready": eligible,
        "rank_eligible": eligible,
        "selection_probability": 0.61 if eligible else 0.53,
        "conditional_no_push_probability": 0.61 if eligible else 0.53,
        "push_probability": 0.0,
        "grade": "B" if eligible else "PASS",
        "tier": "SOLID" if eligible else "NO PLAY",
        "projected_total": 55.2,
        "analysis_line": 50.5,
        "projection_line_distance": 4.7,
        "reliability": 0.84,
        "feature_coverage": 0.86,
    }


def test_final_card_shows_selection_grade_and_zero_line_weight():
    html = hub._final_card(_game(), _final())

    assert "FINAL OVER/UNDER SELECTION" in html
    assert "OVER" in html
    assert "61.0%" in html
    assert "GRADE" not in html or "B" in html
    assert "Projected total" in html
    assert "Analysis line" in html
    assert "0%" in html
    assert "Line projection weight" in html


def test_gated_final_card_fails_closed():
    html = hub._final_card(
        _game(),
        {"ready": False, "reasons": ["game is not verified pregame"]},
    )

    assert "FINAL SELECTION GATED" in html
    assert "game is not verified pregame" in html
    assert "No final Over/Under selection is invented" in html


def test_top_card_contains_rank_side_matchup_line_and_projection():
    row = {
        "rank": 1,
        "game": _game(),
        "final": _final(),
    }

    html = hub._top_card(row)

    assert "#1" in html
    assert "OVER" in html
    assert "Oklahoma @ Michigan" in html
    assert "line 50.5" in html
    assert "projected 55.2" in html
    assert "61.0%" in html


def test_line_board_defaults_only_selected_game_to_use():
    games = [
        {
            "identity_key": "a",
            "away_team": "A",
            "home_team": "B",
            "kickoff_et": "12:00 PM ET",
        },
        {
            "identity_key": "b",
            "away_team": "C",
            "home_team": "D",
            "kickoff_et": "3:30 PM ET",
        },
    ]

    rows = hub._line_board_rows(games, "b", 57.5)

    assert rows[0]["Use"] is False
    assert rows[0]["Analysis Line"] == 50.5
    assert rows[1]["Use"] is True
    assert rows[1]["Analysis Line"] == 57.5
    assert rows[1]["Identity"] == "b"


def test_editor_records_accepts_plain_list():
    rows = [{"Use": True, "Identity": "x", "Analysis Line": 50.5}]
    assert hub._editor_records(rows) == rows


def test_step9_hub_has_manual_line_board_and_no_sportsbook_or_ev_layer():
    source = inspect.getsource(hub).lower()

    assert hub.FROZEN_OVER_UNDER_HUB == "cfb_over_under_hub_v2"
    assert hub.MARKET == "Over/Under"

    required = (
        "st.data_editor",
        "run over/under scan",
        "final_model.rank_slate",
        "slate.scan_slate",
        "manual comparison thresholds",
        "top-5",
    )
    for token in required:
        assert token.lower() in source

    forbidden = (
        "sportsbook_price",
        "market_probability",
        "expected_value",
        "import numpy",
        "np.random",
        "monte carlo simulation",
    )
    for token in forbidden:
        assert token.lower() not in source
