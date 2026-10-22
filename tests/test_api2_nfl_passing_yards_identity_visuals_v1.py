from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_professional_v1 as page
from sports_api.api import nfl_passing_yards_page_v1 as api


ROOT = Path(__file__).resolve().parents[1]


def _player() -> dict:
    return {
        "player_id": "kyre:nfl:player:00-000001",
        "qb_name": "Test Quarterback",
        "team_abbr": "NE",
        "team_name": "New England Patriots",
        "opponent_abbr": "CHI",
        "opponent_team_id": "kyre:nfl:team:CHI",
        "identity_visuals": {
            "canonical_player_id": "kyre:nfl:player:00-000001",
            "source_player_id": "00-000001",
            "identity_verified": True,
            "headshot_url": "https://images.example.test/qb.png",
            "headshot_provider": "NFLverse",
            "team_logo_url": "https://static.www.nfl.com/t_q-best/league/api/clubs/logos/NE.png",
            "team_logo_provider": "NFL Official",
            "opponent_logo_url": "https://static.www.nfl.com/t_q-best/league/api/clubs/logos/CHI.png",
            "opponent_logo_provider": "NFL Official",
        },
        "profile": {
            "passing_yards_per_game": 250.0,
            "attempts_per_game": 33.0,
            "yards_per_attempt": 7.58,
            "completion_pct": 66.5,
            "games": 6,
            "recent3_yards": 780.0,
        },
        "context_projection": {"context_projection_yards": 257.2},
        "distribution": {
            "confidence": "MEDIUM",
            "thresholds": [
                {"ready": True, "threshold": n, "over_probability": 0.55}
                for n in (200, 225, 250, 275, 300)
            ],
        },
        "market": {"line": 249.5},
        "market_evaluation": {
            "model_under_probability": 0.45,
            "model_over_probability": 0.55,
            "lean": "OVER",
            "grade": "B",
        },
        "pass_defense": {
            "rank": 22,
            "grade": "FAVORABLE",
            "pass_yards_allowed_per_game": 241.0,
            "recent3_pass_yards_allowed": 252.0,
        },
        "qb_vs_team_history": {"available": False, "message": "No verified prior matchup history"},
        "why": {
            "volume": {"value": 34, "label": "Expected attempts"},
            "efficiency": {"value": 7.5, "label": "Expected YPA"},
            "pressure": {"value": -1.5, "label": "Pressure adjustment yards"},
            "defense": {"value": 22, "label": "FAVORABLE pass matchup"},
        },
    }


def test_identity_visuals_bind_exact_gsis_team_and_official_nfl_logos() -> None:
    rows = [
        {"season": 2026, "week": 8, "team": "NE", "full_name": "Test Quarterback", "gsis_id": "00-000001", "headshot_url": "https://images.example.test/qb.png"},
        {"season": 2026, "week": 8, "team": "CHI", "full_name": "Wrong Team", "gsis_id": "00-000001", "headshot_url": "https://images.example.test/wrong.png"},
    ]
    result = api.build_identity_visuals(
        team="NE",
        opponent="CHI",
        player_source_id="00-000001",
        qb_name="Test Quarterback",
        season=2026,
        week=8,
        roster_rows=rows,
    )
    assert result["canonical_player_id"] == "kyre:nfl:player:00-000001"
    assert result["identity_verified"] is True
    assert result["headshot_url"] == "https://images.example.test/qb.png"
    assert result["headshot_provider"] == "NFLverse"
    assert result["team_logo_url"].endswith("/NE.png")
    assert result["opponent_logo_url"].endswith("/CHI.png")
    assert result["team_logo_provider"] == "NFL Official"
    assert result["opponent_logo_provider"] == "NFL Official"


def test_identity_visuals_fail_soft_without_exact_player_match() -> None:
    result = api.build_identity_visuals(
        team="NE",
        opponent="CHI",
        player_source_id="00-missing",
        qb_name="Missing Quarterback",
        season=2026,
        week=8,
        roster_rows=[],
    )
    assert result["identity_verified"] is False
    assert result["headshot_url"] is None
    assert result["canonical_player_id"] == "kyre:nfl:player:00-missing"
    assert result["identity_reason"] == "Exact NFLverse GSIS/team identity unavailable"


def test_renderer_places_verified_identity_on_all_major_qb_sections() -> None:
    player = _player()
    for html in (
        page._market_board(player),
        page._profile_card(player),
        page._matchup_card(player),
        page._drivers(player),
        page._ladder(player),
    ):
        assert "kyre:nfl:player:00-000001" in html
        assert "https://images.example.test/qb.png" in html
        assert "/NE.png" in html

    matchup = page._matchup_card(player)
    assert "/CHI.png" in matchup


def test_team_badge_uses_real_logo_and_never_substitutes_missing_data_with_zero() -> None:
    html = page._team_badge(
        team_name="New England Patriots",
        team_abbr="NE",
        logo_url="https://static.www.nfl.com/t_q-best/league/api/clubs/logos/NE.png",
    )
    assert '<img' in html
    assert "/NE.png" in html
    assert "New England Patriots" in html
    assert ">0<" not in html


def test_identity_enrichment_obeys_nfl_source_rule() -> None:
    source = (ROOT / "sports_api" / "api" / "nfl_passing_yards_page_v1.py").read_text(encoding="utf-8").lower()
    assert "nflverse" in source
    assert "static.www.nfl.com" in source
    assert "espn" not in source
    assert "sgo" not in source
    assert "missing_to_zero" in source
