from pathlib import Path

import nfl_passing_yards_hub_v24 as v24


def _identity(*, away_verified=True, home_verified=True, away_abbr="TB", home_abbr="CIN", away_athlete="246", home_athlete="3915511"):
    return {
        "away": {
            "identity_verified": away_verified,
            "team_id": "27",
            "abbr": away_abbr,
            "team": "Tampa Bay Buccaneers",
            "qb1": {"athlete_id": away_athlete, "name": "Baker Mayfield"},
        },
        "home": {
            "identity_verified": home_verified,
            "team_id": "4",
            "abbr": home_abbr,
            "team": "Cincinnati Bengals",
            "qb1": {"athlete_id": home_athlete, "name": "Joe Burrow"},
        },
    }


def test_v24_is_visual_only_wrapper_over_frozen_v23():
    assert v24.FROZEN_PRIOR == "nfl_passing_yards_hub_v23"
    assert "MATCHUP CONTEXT" in v24.MODEL_VERSION


def test_exact_matchup_visuals_use_verified_away_home_identity_only():
    visuals = v24._exact_matchup_visuals(_identity())
    assert visuals[0] == {
        "ready": True,
        "side": "away",
        "team_abbr": "TB",
        "opponent_abbr": "CIN",
        "venue_token": "@",
    }
    assert visuals[1] == {
        "ready": True,
        "side": "home",
        "team_abbr": "CIN",
        "opponent_abbr": "TB",
        "venue_token": "vs",
    }

    assert v24._exact_matchup_visuals(_identity(away_verified=False))[0]["ready"] is False
    assert v24._exact_matchup_visuals(_identity(home_verified=False))[1]["ready"] is False
    assert v24._exact_matchup_visuals(_identity(away_abbr="TAMPA BAY"))[0]["ready"] is False
    assert v24._exact_matchup_visuals(_identity(away_athlete="Baker Mayfield"))[0]["ready"] is False


def test_matchup_text_shows_home_away_context():
    away, home = v24._exact_matchup_visuals(_identity())
    assert v24._matchup_text(away) == "TB • @ CIN"
    assert v24._matchup_text(home) == "CIN • vs TB"
    assert v24._matchup_text({"ready": False}) == ""


def test_matchup_injection_preserves_market_card_content():
    original = (
        '<section class="kpy10-card"><div class="kpy10-top">'
        '<div><div class="kpy10-name">Baker Mayfield • Market Evaluation</div>'
        '<div class="kpy10-sub">Kyre Sports API • FanDuel • projection influence remains 0.0%</div></div>'
        '<div class="kpy10-grade c">C • WATCH</div></div>'
        '<div class="kpy10-metrics">MARKET-LINE-AND-EV-SENTINEL</div></section>'
    )
    visual = v24._exact_matchup_visuals(_identity())[0]
    rendered = v24._inject_matchup_context(original, visual)
    assert '<div class="kpy24-matchup">TB • @ CIN</div>' in rendered
    assert "Kyre Sports API • FanDuel • projection influence remains 0.0%" in rendered
    assert "MARKET-LINE-AND-EV-SENTINEL" in rendered
    assert rendered.count("kpy10-card") == original.count("kpy10-card")
    assert v24._inject_matchup_context(original, {"ready": False}) == original


def test_router_keeps_prior_contracts_and_advances_passing_yards_to_v24():
    source = Path("nfl_hub_v35.py").read_text()
    assert "from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub" in source
    assert "from nfl_passing_yards_hub_v21 import render_nfl_passing_yards_hub as render_v21" in source
    assert "from nfl_passing_yards_hub_v22 import render_nfl_passing_yards_hub as render_v22" in source
    assert "return render_v22()" in source
    assert "from nfl_passing_yards_hub_v23 import render_nfl_passing_yards_hub as render_v23" in source
    assert "return render_v23()" in source
    assert "from nfl_passing_yards_hub_v24 import render_nfl_passing_yards_hub as render_v24" in source
    assert "return render_v24()" in source
    assert "return base.render_nfl_hub(market)" in source


def test_v24_has_no_network_client_or_market_math_implementation():
    source = Path("nfl_passing_yards_hub_v24.py").read_text()
    lower = source.lower()
    assert "import requests" not in source
    assert "evaluate_market(" not in source
    assert "projection_yards" not in source
    assert "over_ev" not in source
    assert "under_ev" not in source
    assert "no fuzzy matching" in lower
    assert "no synthetic ids" in lower
    assert "sportsbook projection influence remains" in lower
    assert "stake sizing remains off" in lower
