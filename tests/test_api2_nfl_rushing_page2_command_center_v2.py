from __future__ import annotations

from importlib import import_module

import pandas as pd


slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
page2 = import_module("nfl_rushing_yards_professional_v1")


def _play_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"game_id":"g1","season":2026,"season_type":"REG","week":1,"game_date":"2026-09-10","posteam":"ATL","defteam":"CAR","no_play":0,"rusher_player_id":"p1","rusher_player_name":"Lead Back","rush_attempt":1,"rushing_yards":12,"rush_touchdown":0,"epa":0.5,"success":1,"yardline_100":50,"qtr":1,"score_differential":0},
            {"game_id":"g1","season":2026,"season_type":"REG","week":1,"game_date":"2026-09-10","posteam":"ATL","defteam":"CAR","no_play":0,"rusher_player_id":"p1","rusher_player_name":"Lead Back","rush_attempt":1,"rushing_yards":-1,"rush_touchdown":0,"epa":-0.2,"success":0,"yardline_100":45,"qtr":2,"score_differential":-3},
            {"game_id":"g1","season":2026,"season_type":"REG","week":1,"game_date":"2026-09-10","posteam":"ATL","defteam":"CAR","no_play":0,"rusher_player_id":"p1","rusher_player_name":"Lead Back","rush_attempt":1,"rushing_yards":4,"rush_touchdown":0,"epa":0.1,"success":1,"yardline_100":18,"qtr":3,"score_differential":7},
            {"game_id":"g1","season":2026,"season_type":"REG","week":1,"game_date":"2026-09-10","posteam":"ATL","defteam":"CAR","no_play":0,"rusher_player_id":"p1","rusher_player_name":"Lead Back","rush_attempt":1,"rushing_yards":6,"rush_touchdown":1,"epa":0.2,"success":1,"yardline_100":4,"qtr":4,"score_differential":10},
            {"game_id":"g1","season":2026,"season_type":"REG","week":1,"game_date":"2026-09-10","posteam":"ATL","defteam":"CAR","no_play":0,"rusher_player_id":"p1","rusher_player_name":"Lead Back","rush_attempt":1,"rushing_yards":2,"rush_touchdown":0,"epa":-0.1,"success":0,"yardline_100":30,"qtr":4,"score_differential":-7},
        ]
    )


def _game_rows() -> list[dict]:
    player_attempts = [10, 12, 14, 16, 18]
    player_yards = [40, 60, 70, 30, 80]
    opponent = ["TB", "NO", "TB", "NO", "TB"]
    rows: list[dict] = []
    for idx, (attempts, yards, opp) in enumerate(zip(player_attempts, player_yards, opponent), start=1):
        rows.append({
            "source_game_id": f"g{idx}", "game_date": f"2026-09-{idx+9:02d}", "week": idx,
            "team_abbr": "ATL", "opponent_abbr": opp, "player_source_id": "p1", "player_name": "Lead Back",
            "attempts": attempts, "rushing_yards": yards, "rushing_touchdowns": 0,
            "explosive_runs": 2, "stuffed_runs": 1, "successful_runs": max(1, attempts // 2),
            "rush_epa": 1.5, "red_zone_attempts": 3, "goal_line_attempts": 1,
            "fourth_quarter_attempts": 4, "leading_attempts": 6, "trailing_attempts": 3,
            "advanced_sample_available": True,
        })
        rows.append({
            "source_game_id": f"g{idx}", "game_date": f"2026-09-{idx+9:02d}", "week": idx,
            "team_abbr": "ATL", "opponent_abbr": opp, "player_source_id": "p2", "player_name": "Backup Back",
            "attempts": 5, "rushing_yards": 20, "rushing_touchdowns": 0,
            "advanced_sample_available": False,
        })
    return rows


def _market(line: float | None = 50.0) -> dict:
    if line is None:
        return {"status":"MARKET_NOT_POSTED","sportsbook":None,"line":None,"over_odds":None,"under_odds":None,"timestamp":None}
    return {"status":"VERIFIED","sportsbook":"FanDuel","line":line,"over_odds":-110,"under_odds":-110,"timestamp":"2026-10-23T00:00:00Z"}


def test_pbp_optional_advanced_columns_are_requested():
    for name in ("epa", "success", "yardline_100", "qtr", "score_differential"):
        assert name in slate.PBP_COLUMNS


def test_player_game_rows_derive_verified_advanced_rushing_context():
    rows = slate._player_game_rows(_play_rows())
    assert len(rows) == 1
    row = rows[0]
    assert row["attempts"] == 5
    assert row["explosive_runs"] == 1
    assert row["stuffed_runs"] == 1
    assert row["successful_runs"] == 3
    assert row["red_zone_attempts"] == 2
    assert row["goal_line_attempts"] == 1
    assert row["fourth_quarter_attempts"] == 2
    assert row["leading_attempts"] == 2
    assert row["trailing_attempts"] == 2
    assert round(row["rush_epa"], 3) == 0.5
    assert row["advanced_sample_available"] is True


def test_page2_summary_helpers_are_field_safe_and_market_aware():
    rows = _game_rows()
    workload = slate.build_workload_intelligence("p1", "ATL", rows)
    assert workload["season_carries_per_game"] == 14.0
    assert workload["l3_carries_per_game"] == 16.0
    assert workload["l5_carries_per_game"] == 14.0
    assert round(workload["team_rush_attempt_share"], 3) == round(70 / 95, 3)
    assert workload["workload_trend"] == "RISING"

    recent = slate.build_recent_form("p1", rows, _market(50.0))
    assert recent["season_average"] == 56.0
    assert recent["l3_average"] == 60.0
    assert recent["l5_average"] == 56.0
    assert recent["median"] == 60.0
    assert recent["floor"] == 30.0
    assert recent["ceiling"] == 80.0
    assert recent["current_line_hit_rate"] == 0.6

    pending = slate.build_recent_form("p1", rows, _market(None))
    assert pending["current_line_hit_rate"] is None
    assert pending["hit_rate_status"] == "MARKET_NOT_POSTED"


def test_comparable_matchups_and_advanced_efficiency_use_verified_context():
    rows = _game_rows()
    defenses = {
        "CAR": {"grade":"FAVORABLE"},
        "TB": {"grade":"FAVORABLE"},
        "NO": {"grade":"TOUGH"},
    }
    comps = slate.build_comparable_matchups("p1", "CAR", rows, defenses)
    assert comps["status"] == "VERIFIED"
    assert comps["target_grade"] == "FAVORABLE"
    assert comps["games"] == 3
    assert all(row["opponent_abbr"] == "TB" for row in comps["games_detail"])

    advanced = slate.build_advanced_efficiency("p1", rows)
    assert advanced["status"] == "VERIFIED_DERIVED"
    assert round(advanced["explosive_run_rate"], 3) == round(10 / 70, 3)
    assert round(advanced["stuff_rate"], 3) == round(5 / 70, 3)
    assert round(advanced["success_rate"], 3) == round(35 / 70, 3)
    assert round(advanced["rush_epa_per_attempt"], 3) == round(7.5 / 70, 3)
    assert advanced["goal_line_carries"] == 5


def test_page2_detail_blocks_include_decision_evidence_and_semantic_states():
    rows = _game_rows()
    defenses = {
        "CAR": {"grade":"FAVORABLE", "rank":27, "rush_yards_allowed_per_game":130.0, "yards_per_carry_allowed":4.6},
        "TB": {"grade":"FAVORABLE"},
        "NO": {"grade":"TOUGH"},
    }
    blocks = slate.build_page2_detail_blocks(
        player={"player_source_id":"p1","player_name":"Lead Back","role":"RB1","team_abbr":"ATL"},
        opponent="CAR",
        game_rows=rows,
        defenses=defenses,
        market=_market(50.0),
        projection={"ready":True,"projection_yards":65.0,"expected_carries":15.5,"expected_yards_per_carry":4.2,"sportsbook_influence":0.0},
        over_probability=0.68,
        under_probability=0.32,
        favored_side="OVER",
        confidence="HIGH",
    )
    for key in (
        "decision", "workload_intelligence", "recent_form", "game_script",
        "comparable_matchups", "advanced_efficiency", "market_intelligence",
        "personnel", "final_read",
    ):
        assert key in blocks
    assert blocks["decision"]["side"] == "OVER"
    assert blocks["decision"]["probability"] == 0.68
    assert blocks["market_intelligence"]["opening_line_status"] == "OPENING_LINE_NOT_CAPTURED"
    assert blocks["market_intelligence"]["movement_status"] == "MOVEMENT_HISTORY_NOT_CAPTURED"
    assert blocks["personnel"]["status"] == "PERSONNEL_VERIFICATION_PENDING"
    assert blocks["game_script"]["weather_status"] == "WEATHER_VERIFICATION_PENDING"
    assert blocks["final_read"]["supporting_factors"]


def test_renderer_is_decision_first_professional_and_zero_blank_safe():
    detail = {
        "player_name":"Lead Back", "role":"RB1", "team_abbr":"ATL", "opponent_abbr":"CAR", "home_away":"HOME",
        "profile":{"carries_per_game":14.0,"rushing_yards_per_game":56.0,"yards_per_carry":4.0,"last5_average":56.0,"recent_games":[]},
        "projection":{"ready":True,"projection_yards":65.0,"expected_carries":15.5,"expected_yards_per_carry":4.2,"sportsbook_influence":0.0},
        "opponent_run_defense":{"grade":"FAVORABLE","rank":27,"rush_yards_allowed_per_game":130.0,"yards_per_carry_allowed":4.6,"rush_attempts_allowed_per_game":28.0,"explosive_run_rate_allowed":0.14,"stuff_rate":0.08,"success_rate_allowed":0.52,"rush_epa_allowed_per_attempt":0.06},
        "matchup_history":{"status":"FIRST_CAREER_MATCHUP","display":"First career matchup","games_detail":[]},
        "market":_market(50.0),
        "availability":{"status":"DATA_UNAVAILABLE","display":"Availability verification pending"},
        "environment":{"status":"PREGAME","display":"Pregame","kickoff_et":"2026-10-25T13:00:00-04:00"},
        "decision":{"side":"OVER","probability":0.68,"confidence":"HIGH","line":50.0,"projection":65.0,"edge":15.0,"expected_carries":15.5,"expected_ypc":4.2},
        "workload_intelligence":{"season_carries_per_game":14.0,"l3_carries_per_game":16.0,"l5_carries_per_game":14.0,"team_rush_attempt_share":0.737,"workload_trend":"RISING","red_zone_carries":15,"goal_line_carries":5,"fourth_quarter_carries":20,"leading_carries":30,"trailing_carries":15},
        "recent_form":{"season_average":56.0,"l3_average":60.0,"l5_average":56.0,"median":60.0,"floor":30.0,"ceiling":80.0,"current_line_hit_rate":0.6,"hit_rate_status":"VERIFIED"},
        "game_script":{"status":"VERIFIED_DERIVED","team_rush_attempts_per_game":19.0,"player_leading_carry_share":0.429,"player_trailing_carry_share":0.214,"player_fourth_quarter_carry_share":0.286,"spread_status":"GAME_SPREAD_NOT_VERIFIED","total_status":"GAME_TOTAL_NOT_VERIFIED","weather_status":"WEATHER_VERIFICATION_PENDING"},
        "comparable_matchups":{"status":"VERIFIED","target_grade":"FAVORABLE","games":1,"average_rushing_yards":70.0,"games_detail":[{"game_date":"2026-09-11","opponent_abbr":"TB","attempts":14,"rushing_yards":70}]},
        "advanced_efficiency":{"status":"VERIFIED_DERIVED","explosive_run_rate":0.143,"stuff_rate":0.071,"success_rate":0.5,"rush_epa_per_attempt":0.107,"red_zone_carries":15,"goal_line_carries":5},
        "market_intelligence":{"status":"VERIFIED","sportsbook":"FanDuel","current_line":50.0,"over_odds":-110,"under_odds":-110,"opening_line_status":"OPENING_LINE_NOT_CAPTURED","movement_status":"MOVEMENT_HISTORY_NOT_CAPTURED"},
        "personnel":{"status":"PERSONNEL_VERIFICATION_PENDING","display":"Personnel verification pending"},
        "final_read":{"supporting_factors":["Kyre projection is 15.0 yards above the verified market line."],"risk_factors":["Personnel verification is still pending."],"unresolved":["Weather verification pending."],"summary":"Kyre leans OVER from verified workload, efficiency, and matchup evidence."},
        "source_lineage":{"workload":"nflverse play-by-play derived","market":"FanDuel","projection":"market-blind model"},
    }
    html = page2.build_rushing_detail_html(detail)
    for label in (
        "DECISION COCKPIT", "WORKLOAD INTELLIGENCE", "RECENT FORM",
        "OPPONENT RUN DEFENSE", "GAME SCRIPT", "MATCHUP + COMPARABLE HISTORY",
        "ADVANCED EFFICIENCY", "MARKET + PERSONNEL", "FINAL KYRE READ",
    ):
        assert label in html
    assert "OVER" in html and "68%" in html and "+15.0" in html
    assert "N/A" not in html
    assert "Unavailable" not in html
    assert "Kyre projection is 15.0 yards above the verified market line." in html


def test_modified_production_path_has_no_banned_provider_dependency():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for path in (root / "sports_api/api/nfl_rushing_yards_slate_v1.py", root / "nfl_rushing_yards_professional_v1.py"):
        source = path.read_text(encoding="utf-8").upper()
        for token in ("SGO", "ESPN", "ESPN BET"):
            assert token not in source
