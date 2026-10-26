from __future__ import annotations

from pathlib import Path

import sports_api.nfl_rushing_yards_page2_enrichment_v1 as enrich

ROOT = Path(__file__).resolve().parents[1]


def test_injury_parser_accepts_nfl_amp_nickname_headings() -> None:
    html = '''<h2>Cowboys</h2><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
    <tr><td>Drew Shelton</td><td>T</td><td>Hamstring</td><td>Did Not Participate In Practice</td><td>Out</td></tr></table>
    <h2>Eagles</h2><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
    <tr><td>Saquon Barkley</td><td>RB</td><td>Hamstring</td><td>Full Participation in Practice</td><td>Questionable</td></tr></table>'''
    report = enrich.parse_official_nfl_injury_html(html)
    assert report["DAL"]["rows"][0]["player_name"] == "Drew Shelton"
    assert report["PHI"]["rows"][0]["game_status"] == "QUESTIONABLE"


def test_direct_fanduel_event_match_uses_teams_and_kickoff_without_espn() -> None:
    landing = {"attachments": {"events": {
        "1": {"eventId": "fd1", "name": "Dallas Cowboys @ Philadelphia Eagles", "openDate": "2026-10-27T00:15:00Z"},
        "2": {"eventId": "fd2", "name": "New York Giants @ Washington Commanders", "openDate": "2026-10-27T00:15:00Z"},
    }}}
    hit = enrich.match_fanduel_event(landing, away="DAL", home="PHI", kickoff="2026-10-26T20:15:00-04:00")
    assert hit["provider_event_id"] == "fd1"
    assert hit["away"] == "DAL" and hit["home"] == "PHI"


def test_direct_fanduel_game_market_parser_extracts_spread_and_total() -> None:
    payload = {"attachments": {"markets": {
        "s1": {"marketId": "s1", "marketName": "Spread", "marketStatus": "OPEN", "inPlay": False, "eventId": "fd1", "runners": [
            {"result": {"type": "AWAY"}, "handicap": 2.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}}},
            {"result": {"type": "HOME"}, "handicap": -2.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}}},
        ]},
        "t1": {"marketId": "t1", "marketName": "Total Points", "marketStatus": "OPEN", "inPlay": False, "eventId": "fd1", "runners": [
            {"runnerName": "Over 47.5", "handicap": 47.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}}},
            {"runnerName": "Under 47.5", "handicap": 47.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": -110}}},
        ]},
    }}}
    row = enrich.parse_direct_fanduel_game_markets(payload, provider_event_id="fd1")
    assert row["sportsbook"] == "FanDuel"
    assert row["away_spread"] == 2.5
    assert row["home_spread"] == -2.5
    assert row["total"] == 47.5


def test_no_banned_provider_dependency() -> None:
    source = (ROOT / "sports_api" / "nfl_rushing_yards_page2_enrichment_v1.py").read_text(encoding="utf-8").upper()
    for banned in ("ESPN BET", "SGO", "SITE.API.ESPN", "ESPN.COM"):
        assert banned not in source
