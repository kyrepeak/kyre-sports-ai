from pathlib import Path

from nfl_prop_analytics_page2_unified_roster_v1 import (
    _player_card,
    _player_headshot_url,
    _team_column,
)

SRC = Path("nfl_prop_analytics_page2_unified_roster_v1.py").read_text()


def test_exact_id_headshot_fallback():
    url = _player_headshot_url({"espn_id": "3915511", "headshot_url": ""})
    assert url == "https://a.espncdn.com/i/headshots/nfl/players/full/3915511.png"


def test_explicit_verified_headshot_wins():
    url = _player_headshot_url({
        "espn_id": "3915511",
        "headshot_url": "https://example.com/verified.png",
    })
    assert url == "https://example.com/verified.png"


def test_player_card_is_an_identity_card():
    row = {
        "espn_id": "3915511",
        "name": "Joe Burrow",
        "team": "CIN",
        "position": "QB",
        "jersey_number": "9",
        "headshot_url": "",
        "depth_role": "QB1 • STARTER",
        "availability_state": "PENDING",
        "availability_label": "GAME-DAY PENDING",
        "verified": True,
        "source_count": 2,
        "depth_verified": True,
        "depth_rank": 1,
    }
    html = _player_card(row)
    assert 'data-prop-page2-player-id-card="v1"' in html
    assert 'data-prop-page2-unified-player-id="3915511"' in html
    assert 'data-prop-page2-player-headshot="v1"' in html
    assert "headshots/nfl/players/full/3915511.png" in html
    assert "ESPN ID 3915511" in html
    assert "Joe Burrow" in html
    assert "QB1 • STARTER" in html
    assert "GAME-DAY PENDING" in html


def test_team_column_has_exact_team_logo():
    truth = {
        "team": "CIN",
        "players": [],
        "by_position": {"QB": [], "RB": [], "WR": [], "TE": []},
    }
    html = _team_column(truth, "Bengals", "ALL")
    assert 'data-prop-page2-roster-team-logo="v1"' in html
    assert 'data-prop-page2-roster-team-logo-team="CIN"' in html
    assert "Bengals logo" in html


def test_identity_visual_patch_is_presentation_only():
    assert "from nfl_prop_analytics_schedule_v1 import team_logo_url" in SRC
    assert "load_verified_roster_truth" in SRC
    assert "load_availability_depth_truth" in SRC
    assert "eligible_players" not in SRC
    assert "build_player_handoff" not in SRC
    assert "PRESENTATION_ONLY = True" in SRC
    assert "MAY_MODIFY_PASSING_YARDS = False" in SRC
