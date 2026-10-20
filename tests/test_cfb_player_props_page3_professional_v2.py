from __future__ import annotations

from pathlib import Path

import cfb_player_props_page3_v1 as page3

ROOT = Path(__file__).resolve().parents[1]


def test_professional_v2_compacts_page_into_dashboard_grids_and_source_audit():
    source = (ROOT / "cfb_player_props_page3_v1.py").read_text()
    for token in (
        "PROFESSIONAL ANALYTICS V2",
        "MATCHUP INTELLIGENCE",
        "SPORTSBOOK MARKET",
        "MARKET MOVEMENT",
        "RECENT PRODUCTION",
        "DATA QUALITY & SOURCES",
        "Source Audit",
        "cfbpp3-stat-grid",
        "cfbpp3-evidence-grid",
        "cfbpp3-table",
    ):
        assert token in source
    assert "st.metric(" not in source


def test_professional_v2_formats_verified_timestamp_for_humans():
    assert page3._friendly_timestamp("2026-10-20T22:00:49.979325Z") == "Updated 3:00 PM MST"
    assert page3._friendly_timestamp("") == "Update time unavailable"


def test_professional_v2_never_surfaces_internal_opponent_id_in_recent_table():
    frame = page3._recent_table({
        "rows": (
            {"game_date": "2026-10-17", "opponent_team_id": "2229", "value": 312},
        )
    })
    assert "2229" not in frame.to_string()
    assert frame.loc[0, "Opponent"] == "—"


def test_professional_v2_team_history_uses_user_facing_matchup_not_internal_ids():
    frame = page3._team_history_table(
        {
            "rows": (
                {"date": "2025-11-08", "opponent_team_id": "2229", "away_points": 30, "home_points": 56, "combined_total": 86},
            )
        },
        {"away_team": "Middle Tennessee", "home_team": "FIU"},
    )
    assert list(frame.columns) == ["Date", "Matchup", "Score", "Total"]
    assert frame.loc[0, "Matchup"] == "Middle Tennessee vs FIU"
    assert frame.loc[0, "Score"] == "30–56"
    assert "2229" not in frame.to_string()


def test_professional_v2_keeps_model_and_input_contracts_frozen():
    source = (ROOT / "cfb_player_props_page3_v1.py").read_text()
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE" in source
    assert "reline_page3_analysis" in source
    assert "build_professional_view" in source
    assert "st.number_input" not in source
    assert "st.text_input" not in source
