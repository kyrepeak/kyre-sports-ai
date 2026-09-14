from __future__ import annotations

import nfl_receiving_yards_hub_v10 as page


def test_v10_rewrites_inherited_v7_badge_to_final_step(monkeypatch):
    monkeypatch.setattr(
        page,
        "_ORIGINAL_DETAILED_CARD_V7",
        lambda *args: '<span class="krecv7-badge">Page Step 7 / 10</span>',
    )
    monkeypatch.setattr(
        page,
        "_grade_for_team_opponent",
        lambda *args: {
            "tier": "MEDIUM",
            "score": 0,
            "available": False,
            "reason": "verified context unavailable",
        },
    )
    html = page._detailed_player_card_v10(
        {"official_athlete_id": "1"},
        {"official_team_id": "2", "opponent_official_team_id": "3"},
        {"team_abbreviation": "OPP"},
    )
    assert "Page Step 7 / 10" not in html
    assert "Page Step 10 / 10" in html
    assert page.PAGE_BUILD_STEP == page.PAGE_BUILD_TOTAL == 10
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
