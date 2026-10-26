from __future__ import annotations

from sports_api import nfl_rushing_yards_page2_live_repair_v1 as repair


def test_injury_parser_accepts_nfl_nickname_headings_and_week_url() -> None:
    html = '''<h3>Cowboys</h3><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
    <tr><td>Drew Shelton</td><td>T</td><td>Hamstring</td><td>Did Not Participate In Practice</td><td>Out</td></tr></table>
    <h3>Eagles</h3><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
    <tr><td>Saquon Barkley</td><td>RB</td><td>Hamstring</td><td>Full Participation in Practice</td><td>Questionable</td></tr>
    <tr><td>Landon Dickerson</td><td>G</td><td>Knee, Pectoral</td><td>Full Participation in Practice</td><td>Questionable</td></tr></table>'''
    report = repair.parse_official_weekly_injuries(html)
    assert report["DAL"]["verified"] is True
    assert report["PHI"]["verified"] is True
    assert report["PHI"]["rows"][0]["player_name"] == "Saquon Barkley"
    assert repair.official_injury_url(2026, 7).endswith("/injuries/league/2026/reg7")


def test_fanduel_full_game_parser_keeps_exact_main_spread_and_total_only() -> None:
    payload = {
        "attachments": {"markets": {
            "1": {"marketType":"MATCH_HANDICAP_(2-WAY)", "marketName":"Point Spread", "runners":[
                {"runnerName":"Dallas Cowboys +4.5", "handicap":4.5, "winRunnerOdds":{"americanDisplayOdds":{"americanOdds":"-105"}}},
                {"runnerName":"Philadelphia Eagles -4.5", "handicap":-4.5, "winRunnerOdds":{"americanDisplayOdds":{"americanOdds":"-115"}}},
            ]},
            "2": {"marketType":"TOTAL_POINTS_(OVER/UNDER)", "marketName":"Total Points", "runners":[
                {"runnerName":"Over 44.5", "handicap":44.5, "winRunnerOdds":{"americanDisplayOdds":{"americanOdds":"-102"}}},
                {"runnerName":"Under 44.5", "handicap":44.5, "winRunnerOdds":{"americanDisplayOdds":{"americanOdds":"-120"}}},
            ]},
            "3": {"marketType":"1ST_HALF_TOTAL_POINTS_(OVER/UNDER)", "marketName":"1st Half Total", "runners":[]},
        }}
    }
    row = repair.parse_fanduel_game_lines(payload, away_name="Dallas Cowboys", home_name="Philadelphia Eagles")
    assert row["away_spread"] == 4.5
    assert row["home_spread"] == -4.5
    assert row["total"] == 44.5
    assert row["sportsbook"] == "FanDuel"


def test_action_network_rush_yards_open_and_current_parser() -> None:
    text = "Javonte Williams Dallas Cowboys Popular Markets Rush Yds u68.5 u64.5-121 o64.5-115 Rush Att u17.5 u16.5-125"
    row = repair.parse_action_rushing_open_current(text, player_name="Javonte Williams")
    assert row["opening_line"] == 68.5
    assert row["current_line"] == 64.5
    assert row["movement"] == -4.0
    assert row["source"] == "Action Network public player props"


def test_final_enrichment_has_no_avoidable_pending_states() -> None:
    detail = {
        "player_name":"Javonte Williams","team_abbr":"DAL","opponent_abbr":"PHI","home_away":"AWAY",
        "market_intelligence":{"sportsbook":"FanDuel","current_line":64.5,"over_odds":-113,"under_odds":-113},
        "game_script":{"spread_status":"GAME_SPREAD_NOT_VERIFIED","total_status":"GAME_TOTAL_NOT_VERIFIED","weather_status":"61°F · 0% precip · 6 mph gust","weather_verification":"VERIFIED"},
        "availability":{"verification":"UNAVAILABLE","display":"Official NFL injury report unavailable"},
        "personnel":{"status":"DATA_UNAVAILABLE","display":"Official personnel report unavailable"},
        "final_read":{"risk_factors":["Personnel verification is still pending."],"unresolved":["Verified line-movement history is not captured by the current feed."]},
    }
    report = {"DAL":{"verified":True,"rows":[]},"PHI":{"verified":True,"rows":[]}}
    out = repair.apply_live_acceptance_repair(
        detail,
        injury_report=report,
        game_lines={"sportsbook":"FanDuel","away_spread":-4.5,"home_spread":4.5,"total":44.5},
        prop_history={"opening_line":68.5,"current_line":64.5,"movement":-4.0,"source":"Action Network public player props"},
    )
    assert out["availability"]["verification"] == "VERIFIED"
    assert out["personnel"]["status"] == "VERIFIED"
    assert "FanDuel" in out["game_script"]["spread_status"]
    assert "44.5" in out["game_script"]["total_status"]
    assert out["market_intelligence"]["opening_line"] == 68.5
    assert out["market_intelligence"]["movement"] == -4.0
    assert not out["final_read"]["risk_factors"]
    assert not out["final_read"]["unresolved"]
