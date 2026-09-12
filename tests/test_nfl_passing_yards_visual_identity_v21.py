from pathlib import Path

import nfl_passing_yards_hub_v21 as v21


def _identity(*, verified=True, team_id="27", abbr="TB", athlete_id="246"):
    return {
        "away": {
            "identity_verified": verified,
            "team_id": team_id,
            "abbr": abbr,
            "team": "Tampa Bay Buccaneers",
            "qb1": {"athlete_id": athlete_id, "name": "Verified QB"},
        },
        "home": {
            "identity_verified": True,
            "team_id": "4",
            "abbr": "CIN",
            "team": "Cincinnati Bengals",
            "qb1": {"athlete_id": "3915511", "name": "Verified QB 2"},
        },
    }


def test_v21_is_visual_only_wrapper_over_frozen_v20():
    assert v21.FROZEN_PRIOR == "nfl_passing_yards_hub_v20"
    assert "TEAM LOGOS" in v21.MODEL_VERSION


def test_exact_team_visuals_require_verified_team_and_qb_ids():
    visuals = v21._exact_team_visuals(_identity())
    assert visuals[0]["ready"] is True
    assert visuals[0]["team_id"] == "27"
    assert visuals[0]["team_abbr"] == "TB"
    assert visuals[0]["athlete_id"] == "246"
    assert visuals[1]["ready"] is True

    assert v21._exact_team_visuals(_identity(verified=False))[0]["ready"] is False
    assert v21._exact_team_visuals(_identity(team_id=""))[0]["ready"] is False
    assert v21._exact_team_visuals(_identity(abbr="TAMPA BAY"))[0]["ready"] is False
    assert v21._exact_team_visuals(_identity(athlete_id="unknown"))[0]["ready"] is False


def test_team_logo_url_comes_only_from_verified_espn_abbreviation():
    visual = v21._exact_team_visuals(_identity())[0]
    assert v21._team_logo_url(visual) == "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png"
    assert v21._team_logo_url({"ready": False, "team_abbr": "TB"}) == ""
    assert v21._team_logo_url({"ready": True, "team_abbr": "TAMPA BAY"}) == ""


def test_logo_injection_preserves_original_market_card_content():
    original = (
        '<section class="kpy10-card"><div class="kpy10-top">'
        '<div><div class="kpy10-name">QB • Market Evaluation</div></div>'
        '<div class="kpy10-grade b">B • VALUE</div></div>'
        '<div class="kpy10-metrics">MARKET-LINE-AND-EV-SENTINEL</div></section>'
    )
    visual = v21._exact_team_visuals(_identity())[0]
    rendered = v21._inject_team_logo(original, visual)
    assert "kpy21-team-logo-slot" in rendered
    assert "teamlogos/nfl/500/tb.png" in rendered
    assert "MARKET-LINE-AND-EV-SENTINEL" in rendered
    assert rendered.count("kpy10-card") == original.count("kpy10-card")

    assert v21._inject_team_logo(original, {"ready": False}) == original


def test_router_advances_only_passing_yards_to_v21():
    source = Path("nfl_hub_v35.py").read_text()
    assert "from nfl_passing_yards_hub_v21 import render_nfl_passing_yards_hub" in source
    assert "return base.render_nfl_hub(market)" in source
    assert "0.0% sportsbook projection influence" in source


def test_v21_has_no_network_client_or_market_math_implementation():
    source = Path("nfl_passing_yards_hub_v21.py").read_text()
    assert "import requests" not in source
    assert "evaluate_market(" not in source
    assert "projection_yards" not in source
    assert "over_ev" not in source
    assert "under_ev" not in source
    assert "no fuzzy matching" in source.lower()
    assert "no synthetic ids" in source.lower()
