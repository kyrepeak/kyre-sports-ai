from __future__ import annotations

from pathlib import Path

import sports_api.nfl_rushing_yards_page2_enrichment_v1 as enrich


ROOT = Path(__file__).resolve().parents[1]


def test_official_nfl_injury_html_resolves_player_and_trench_context() -> None:
    html = '''
    <h3>Dallas Cowboys</h3><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
    <tr><td>Dee Winters</td><td>LB</td><td>Calf</td><td>Did Not Participate In Practice</td><td>Questionable</td></tr></table>
    <h3>Philadelphia Eagles</h3><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
    <tr><td>Landon Dickerson</td><td>G</td><td>Knee</td><td>Limited Participation in Practice</td><td>Questionable</td></tr>
    <tr><td>Saquon Barkley</td><td>RB</td><td>Hamstring</td><td>Limited Participation in Practice</td><td>Questionable</td></tr></table>
    '''
    report = enrich.parse_official_nfl_injury_html(html)
    context = enrich.build_injury_personnel_context(
        report,
        player_name="Saquon Barkley",
        team="PHI",
        opponent="DAL",
    )
    assert context["availability"]["verification"] == "VERIFIED"
    assert context["availability"]["game_status"] == "QUESTIONABLE"
    assert context["availability"]["injury"] == "Hamstring"
    assert context["offensive_line"]["flagged"][0]["player_name"] == "Landon Dickerson"
    assert context["defensive_front"]["flagged"][0]["player_name"] == "Dee Winters"


def test_no_player_row_on_verified_team_report_means_no_official_designation() -> None:
    report = {
        "DAL": {"verified": True, "rows": []},
        "PHI": {"verified": True, "rows": []},
    }
    context = enrich.build_injury_personnel_context(
        report,
        player_name="Javonte Williams",
        team="DAL",
        opponent="PHI",
    )
    assert context["availability"]["verification"] == "VERIFIED"
    assert context["availability"]["game_status"] == "NO OFFICIAL INJURY DESIGNATION"
    assert context["offensive_line"]["verification"] == "VERIFIED"
    assert context["defensive_front"]["verification"] == "VERIFIED"


def test_game_market_parser_keeps_one_book_and_spread_total() -> None:
    payload = {
        "id": "event1",
        "bookmakers": [
            {"key": "fanduel", "title": "FanDuel", "last_update": "2026-10-26T01:00:00Z", "markets": [
                {"key": "spreads", "outcomes": [
                    {"name": "Dallas Cowboys", "point": 2.5, "price": -110},
                    {"name": "Philadelphia Eagles", "point": -2.5, "price": -110},
                ]},
                {"key": "totals", "outcomes": [
                    {"name": "Over", "point": 47.5, "price": -110},
                    {"name": "Under", "point": 47.5, "price": -110},
                ]},
            ]}
        ],
    }
    row = enrich.parse_game_markets(payload, away_name="Dallas Cowboys", home_name="Philadelphia Eagles")
    assert row["sportsbook"] == "FanDuel"
    assert row["away_spread"] == 2.5
    assert row["home_spread"] == -2.5
    assert row["total"] == 47.5


def test_player_prop_history_yields_earliest_verified_line_and_movement() -> None:
    current = {"sportsbook": "FanDuel", "current_line": 64.5}
    snapshots = [
        {"timestamp": "2026-10-24T00:00:00Z", "line": 61.5, "sportsbook": "FanDuel"},
        {"timestamp": "2026-10-25T00:00:00Z", "line": 63.5, "sportsbook": "FanDuel"},
    ]
    out = enrich.build_line_history(current, snapshots)
    assert out["opening_line"] == 61.5
    assert out["movement"] == 3.0
    assert out["movement_status"].startswith("UP +3.0")


def test_history_date_repair_uses_schedule_by_source_game_id() -> None:
    rows = [{"source_game_id": "2025_08_DAL_PHI", "game_date": "", "opponent_abbr": "PHI"}]
    schedule = {"2025_08_DAL_PHI": "2025-10-26"}
    repaired = enrich.repair_history_dates(rows, schedule)
    assert repaired[0]["game_date"] == "2025-10-26"


def test_weather_normalizer_handles_outdoor_and_indoor() -> None:
    outdoor = enrich.normalize_weather({
        "ready": True,
        "provider": "NWS + canonical NFL stadium registry",
        "data": {"indoor": False, "weather_applies": True, "temperature": 52.0, "precipitation": 10.0, "gust": 8.0, "weather_pressure": "LOW"},
    })
    assert outdoor["verification"] == "VERIFIED"
    assert outdoor["temperature_f"] == 52.0
    indoor = enrich.normalize_weather({
        "ready": True,
        "provider": "NWS + canonical NFL stadium registry",
        "data": {"indoor": True, "weather_applies": False, "weather_pressure": "INDOOR"},
    })
    assert indoor["display"] == "INDOORS — WEATHER IMPACT NONE"


def test_detail_v3_successor_is_live_without_mutating_frozen_v2() -> None:
    successor = (ROOT / "sports_api" / "api" / "nfl_rushing_yards_detail_v3.py").read_text(encoding="utf-8")
    entry = (ROOT / "kyre_sports_api_vercel_v1.py").read_text(encoding="utf-8")
    frozen_v2 = (ROOT / "sports_api" / "api" / "nfl_rushing_yards_detail_v2.py").read_text(encoding="utf-8")
    assert "nfl_rushing_yards_page2_enrichment_v1" in successor
    assert "import sports_api.api.nfl_rushing_yards_detail_v3 as nfl_rushing_yards_detail_module" in entry
    assert '"nfl_rushing_yards_detail_v3": True' in entry
    assert '"opening_line": None' in frozen_v2
    assert '"spread_status": "GAME_SPREAD_NOT_VERIFIED"' in frozen_v2
