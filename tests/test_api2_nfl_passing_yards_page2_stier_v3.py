from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


def _card(edge: float = 0.2, over: float = 0.50, under: float = 0.50) -> dict:
    return {
        "player_id":"kyre:nfl:player:00-0039001","qb_name":"D.Maye","team_abbr":"NE","team_name":"New England Patriots",
        "opponent_abbr":"CHI","game_id":"kyre:nfl:game:2026_NE_CHI","game_date":"2026-10-25","game_time":"16:25","home_away":"AWAY",
        "headshot_url":"https://example.com/maye.png","team_logo_url":"https://example.com/ne.png",
        "projection_yards":247.7 if edge == 0.2 else 252.8,"edge_yards":edge,"over_probability":over,"under_probability":under,
        "favored_side":"OVER","confidence":"MEDIUM",
        "market":{"status":"VERIFIED","sportsbook":"FanDuel","line":247.5 if edge == 0.2 else 241.5,"over_odds":-113,"under_odds":-113,"timestamp":"2026-10-22T23:21:19.177497+00:00"},
        "detail":{
            "profile":{"games":6,"passing_yards_per_game":243.8,"attempts_per_game":32.5,"completion_pct":60.0,"yards_per_attempt":7.50,"pass_tds":11,"interceptions":7,"recent_games":[]},
            "season_game_log":[
                {"week":1,"home_away":"AWAY","opponent":"SEA","passing_yards":178,"attempts":36,"completions":23,"pass_tds":1,"interceptions":3},
                {"week":2,"home_away":"HOME","opponent":"PIT","passing_yards":208,"attempts":25,"completions":14,"pass_tds":0,"interceptions":1},
                {"week":3,"home_away":"AWAY","opponent":"JAX","passing_yards":199,"attempts":28,"completions":14,"pass_tds":0,"interceptions":2},
                {"week":4,"home_away":"AWAY","opponent":"BUF","passing_yards":269,"attempts":39,"completions":22,"pass_tds":3,"interceptions":1},
                {"week":5,"home_away":"HOME","opponent":"LV","passing_yards":374,"attempts":35,"completions":26,"pass_tds":4,"interceptions":0},
                {"week":6,"home_away":"HOME","opponent":"NYJ","passing_yards":235,"attempts":32,"completions":18,"pass_tds":3,"interceptions":0},
            ],
            "context_projection":{"context_projection_yards":247.7 if edge == 0.2 else 252.8,"pressure_adjustment_yards":-4.3},
            "distribution":{"confidence":"MEDIUM","sigma_yards":70.9},
            "market":{"ready":True,"sportsbook":"FanDuel","line":247.5 if edge == 0.2 else 241.5,"over_odds":-113,"under_odds":-113,"source_timestamp":"2026-10-22T23:21:19.177497+00:00","books":[{"sportsbook":"FanDuel","line":247.5 if edge == 0.2 else 241.5,"over_odds":-113,"under_odds":-113,"source_timestamp":"2026-10-22T23:21:19.177497+00:00"}],"line_movement":{"ready":False,"sportsbook":"FanDuel"}},
            "market_evaluation":{"ready":True,"lean":"OVER","grade":"CHECK" if edge == 0.2 else "MEDIUM","model_over_probability":over,"model_under_probability":under},
            "pass_defense":{"rank":15,"grade":"MEDIUM","pass_yards_allowed_per_game":228.0,"passing_attempts_allowed_per_game":30.2,"completion_pct_allowed":56.4,"yards_per_attempt_allowed":7.56,"recent3_pass_yards_allowed":237.0,"sack_rate_generated":8.6},
            "qb_vs_team_history":{"available":True,"games":1,"avg_passing_yards":184.0,"avg_attempts":26.0,"completion_pct":57.7,"games_detail":[{"opponent":"CHI","passing_yards":184,"attempts":26,"completions":15,"pass_tds":1,"interceptions":1}]},
            "availability":{"verified":False,"reason":"Official injury/availability data not verified for this request"},
            "game_environment":{"verified":True,"venue":"Soldier Field","roof":"outdoors","surface":"grass","temperature_f":None,"wind_mph":None,"rest_days":4,"source":"NFLverse schedule"},
            "page1_decision_support":{"thesis":{"ready":True,"side":"OVER","line":247.5 if edge == 0.2 else 241.5,"strength":"CHECK" if edge == 0.2 else "MODERATE","narrative":"Verified market line is available, but the evidence does not support a strong Over or Under side." if edge == 0.2 else "Verified evidence favors the Over.","factors":[{"label":"Projection edge","positive":edge>0,"detail":f"{edge:+.1f} yards versus the exact market line"},{"label":"Recent hit rate","positive":False,"detail":"2 of last 5 games"}]},"risk_flags":["High recent passing-yard variance","Availability verification pending","Same-book line history building"]},
        }
    }


def test_v3_successor_exists_and_page1_handoff_activates_it():
    assert importlib.util.find_spec("nfl_passing_yards_page2_command_center_v3") is not None
    source=Path("nfl_passing_yards_simple_qb_grid_v1/__init__.py").read_text()
    assert "nfl_passing_yards_page2_command_center_v3" in source


def test_v3_compacts_recent_performance_into_hit_strip_and_visual_game_rows():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card())
    assert 'class="k3-hitstrip"' in html
    for label in ("LAST 5","LAST 10","SEASON","HOME","AWAY"): assert label in html
    assert "2/5 O" in html and "40%" in html
    assert 'class="k3-yardbar"' in html
    assert 'data-result="OVER"' in html and 'data-result="UNDER"' in html


def test_v3_uses_metric_tiles_for_qb_form_and_opponent_defense():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card())
    assert "QB FORM" in html and "CHI PASS DEFENSE" in html
    assert "243.8" in html and "228.0" in html and "8.6%" in html
    assert 'class="k3-matchupgrid"' in html


def test_v3_humanizes_market_timestamp_and_compacts_line_board():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card())
    assert "2026-10-22T23:21:19.177497+00:00" not in html
    assert "Updated" in html and "UTC" in html
    assert "Opening line history building" in html
    assert "O -113" in html and "U -113" in html


def test_v3_single_matchup_is_compact_summary_and_verified_history_remains_visible():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card())
    assert "Previous matchup vs CHI" in html
    assert "184 YDS" in html and "15/26" in html and "1 TD" in html and "1 INT" in html


def test_v3_weak_market_is_pass_not_false_over_recommendation():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card())
    assert "PASS — NO ACTIONABLE EDGE" in html
    assert "No actionable edge at 247.5" in html
    assert "Model direction: slight OVER" in html
    assert "FINAL DECISION</div><div class=\"k3-decisionmain\">OVER 247.5" not in html


def test_v3_strong_verified_edge_keeps_directional_over_decision():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card(edge=11.3,over=.61,under=.39))
    assert "OVER 241.5" in html
    assert "PASS — NO ACTIONABLE EDGE" not in html


def test_v3_environment_availability_risk_and_top_controls_are_compact():
    p=importlib.import_module("nfl_passing_yards_page2_command_center_v3")
    html=p.build_page2_html(_card())
    assert 'class="k3-envstrip"' in html
    assert "Weather pending" in html and "4 rest days" in html
    assert "Availability not yet verified" in html
    assert 'data-severity="high"' in html and 'data-severity="pending"' in html
    css=p.CSS.replace(" ","").lower()
    assert 'a[data-kyre-universal-top="v2"]{display:none!important}' in css
    assert html.count("↑ TOP") == 0


def test_v3_remains_presentation_only_and_preserves_source_contract():
    source=Path("nfl_passing_yards_page2_command_center_v3.py").read_text()
    assert "requests" not in source
    assert "httpx" not in source
    assert "espn" not in source.lower()
    assert "sgo" not in source.lower()
    assert "Kyre Sports API" in source
