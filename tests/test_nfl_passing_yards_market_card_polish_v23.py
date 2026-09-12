from pathlib import Path

import nfl_passing_yards_hub_v23 as v23


def test_v23_is_css_only_wrapper_over_frozen_v22():
    assert v23.FROZEN_PRIOR == "nfl_passing_yards_hub_v22"
    assert "CARD HEADER POLISH" in v23.MODEL_VERSION


def test_v23_fixes_headshot_flex_stretch_and_keeps_compact_portrait():
    css = v23._POLISH_CSS
    assert ".kpy10-top>.kpy21-team-logo-slot+.kpy22-player-headshot-slot" in css
    assert "flex:0 0 48px!important" in css
    assert "width:48px!important" in css
    assert "height:48px!important" in css
    assert "max-width:48px!important" in css
    assert "border-radius:50%!important" in css


def test_v23_keeps_team_logo_compact_and_header_aligned():
    css = v23._POLISH_CSS
    assert ".kpy21-team-logo-slot" in css
    assert "flex:0 0 36px!important" in css
    assert "align-items:center!important" in css
    assert ".kpy10-grade" in css
    assert "margin-left:auto!important" in css


def test_v23_has_mobile_compact_sizes():
    css = v23._POLISH_CSS
    assert "@media(max-width:820px)" in css
    assert "width:44px!important" in css
    assert "flex-basis:44px!important" in css
    assert "width:32px!important" in css


def test_router_keeps_frozen_v20_v21_v22_contracts_and_advances_to_v23():
    source = Path("nfl_hub_v35.py").read_text()
    assert "from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub" in source
    assert "from nfl_passing_yards_hub_v21 import render_nfl_passing_yards_hub as render_v21" in source
    assert "from nfl_passing_yards_hub_v22 import render_nfl_passing_yards_hub as render_v22" in source
    assert "return render_v22()" in source
    assert "from nfl_passing_yards_hub_v23 import render_nfl_passing_yards_hub as render_v23" in source
    assert "return render_v23()" in source
    assert "return base.render_nfl_hub(market)" in source


def test_v23_has_no_identity_network_or_market_math_implementation():
    source = Path("nfl_passing_yards_hub_v23.py").read_text()
    lower = source.lower()
    assert "import requests" not in source
    assert "resolve_matchup_identity" not in source
    assert "evaluate_market(" not in source
    assert "projection_yards" not in source
    assert "over_ev" not in source
    assert "under_ev" not in source
    assert "sportsbook projection influence remains 0.0%" in lower
    assert "stake sizing remains off" in lower
