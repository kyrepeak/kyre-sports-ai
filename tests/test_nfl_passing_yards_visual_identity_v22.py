from pathlib import Path

import nfl_passing_yards_hub_v22 as v22


def _identity(*, verified=True, team_id="27", athlete_id="246", player_name="Verified QB"):
    return {
        "away": {
            "identity_verified": verified,
            "team_id": team_id,
            "abbr": "TB",
            "team": "Tampa Bay Buccaneers",
            "qb1": {"athlete_id": athlete_id, "name": player_name},
        },
        "home": {
            "identity_verified": True,
            "team_id": "4",
            "abbr": "CIN",
            "team": "Cincinnati Bengals",
            "qb1": {"athlete_id": "3915511", "name": "Verified QB 2"},
        },
    }


def test_v22_is_visual_only_wrapper_over_frozen_v21():
    assert v22.FROZEN_PRIOR == "nfl_passing_yards_hub_v21"
    assert "HEADSHOTS" in v22.MODEL_VERSION


def test_exact_player_visuals_require_verified_exact_ids():
    visuals = v22._exact_player_visuals(_identity())
    assert visuals[0]["ready"] is True
    assert visuals[0]["athlete_id"] == "246"
    assert visuals[0]["team_id"] == "27"
    assert visuals[0]["player_name"] == "Verified QB"
    assert visuals[1]["ready"] is True

    assert v22._exact_player_visuals(_identity(verified=False))[0]["ready"] is False
    assert v22._exact_player_visuals(_identity(team_id=""))[0]["ready"] is False
    assert v22._exact_player_visuals(_identity(athlete_id="Baker Mayfield"))[0]["ready"] is False


def test_player_headshot_url_comes_only_from_verified_numeric_espn_athlete_id():
    visual = v22._exact_player_visuals(_identity())[0]
    assert v22._player_headshot_url(visual) == "https://a.espncdn.com/i/headshots/nfl/players/full/246.png"
    assert v22._player_headshot_url({"ready": False, "athlete_id": "246"}) == ""
    assert v22._player_headshot_url({"ready": True, "athlete_id": "Verified QB"}) == ""


def test_headshot_injection_preserves_original_market_card_content():
    original = (
        '<section class="kpy10-card"><div class="kpy10-top">'
        '<div><div class="kpy10-name">QB • Market Evaluation</div></div>'
        '<div class="kpy10-grade b">B • VALUE</div></div>'
        '<div class="kpy10-metrics">MARKET-LINE-AND-EV-SENTINEL</div></section>'
    )
    visual = v22._exact_player_visuals(_identity())[0]
    rendered = v22._inject_player_headshot(original, visual)
    assert "kpy22-player-headshot-slot" in rendered
    assert "headshots/nfl/players/full/246.png" in rendered
    assert "MARKET-LINE-AND-EV-SENTINEL" in rendered
    assert rendered.count("kpy10-card") == original.count("kpy10-card")

    assert v22._inject_player_headshot(original, {"ready": False}) == original


def test_router_keeps_v20_v21_contracts_and_advances_passing_yards_to_v22():
    source = Path("nfl_hub_v35.py").read_text()
    assert "from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub" in source
    assert "from nfl_passing_yards_hub_v21 import render_nfl_passing_yards_hub as render_v21" in source
    assert "from nfl_passing_yards_hub_v22 import render_nfl_passing_yards_hub as render_v22" in source
    assert "return render_v22()" in source
    assert "return base.render_nfl_hub(market)" in source
    assert "0.0%" in source


def test_v22_has_no_network_client_or_market_math_implementation():
    source = Path("nfl_passing_yards_hub_v22.py").read_text()
    assert "import requests" not in source
    assert "evaluate_market(" not in source
    assert "projection_yards" not in source
    assert "over_ev" not in source
    assert "under_ev" not in source
    assert "no fuzzy matching" in source.lower()
    assert "no synthetic ids" in source.lower()
    assert "player names are display text only" in source.lower()
