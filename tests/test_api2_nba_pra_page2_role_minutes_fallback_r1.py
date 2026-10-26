from __future__ import annotations

import nba_pra_page2_command_center_v3 as page2


def test_verified_recent_minutes_fill_role_when_usage_is_unavailable() -> None:
    context = {
        "player": {},
        "team": "BOS",
        "opponent": "MIA",
        "availability": "AVAILABLE",
        "availability_verification": "VERIFIED",
        "availability_source": "NBA Official Injury Report",
        "teammate_injuries": [],
    }
    games = [
        {"minutes": 36.0, "opponent": "NYK", "pra": 31.0},
        {"minutes": 34.0, "opponent": "DET", "pra": 28.0},
        {"minutes": 35.0, "opponent": "NOP", "pra": 29.0},
    ]

    html = page2._role_availability_html(context, games)

    assert "ROLE & MINUTES" in html
    assert "CORE ROTATION ROLE" in html
    assert "35.0 AVG MIN" in html
    assert "3 VERIFIED RECENT GAMES" in html
    assert "Verified game history" in html
    assert "Usage / team role not currently verified" not in html
    assert "PLAYER AVAILABILITY" in html
    assert "AVAILABLE" in html


def test_role_gap_remains_when_neither_usage_nor_verified_minutes_exist() -> None:
    context = {
        "player": {},
        "team": "BOS",
        "opponent": "MIA",
        "availability": "AVAILABLE",
        "availability_verification": "VERIFIED",
        "availability_source": "NBA Official Injury Report",
        "teammate_injuries": [],
    }

    html = page2._role_availability_html(context, [])

    assert "Usage / team role not currently verified" in html
    assert "ROLE & MINUTES" not in html


def test_sportsbook_projection_influence_stays_frozen() -> None:
    assert page2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
