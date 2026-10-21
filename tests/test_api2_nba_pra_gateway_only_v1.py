from __future__ import annotations

from datetime import datetime, timezone
import inspect


def test_page1_overlay_has_no_legacy_direct_provider_module_dependencies():
    import nba_pra_page1_api_only_v1 as overlay
    source = inspect.getsource(overlay).casefold()
    assert "nba_pra_page1_data_v2" not in source
    assert "nba_pra_page1_data_core_v2" not in source
    assert "nba_pra_page1_sgo_v1" not in source
    assert "sportsgameodds" not in source
    assert "espn" not in source


def test_gateway_schedule_source_has_no_prohibited_provider_dependency():
    import runless_v2.nba_pra_schedule_v1 as schedule
    source = inspect.getsource(schedule).casefold()
    assert "sportsgameodds" not in source
    assert "sgo" not in source
    assert "espn" not in source


def test_gateway_injury_source_has_no_prohibited_provider_dependency():
    import runless_v2.nba_pra_injury_v1 as injury
    source = inspect.getsource(injury).casefold()
    assert "sportsgameodds" not in source
    assert "sgo" not in source
    assert "espn" not in source


def test_page1_uses_gateway_loaders_for_schedule_context_and_injuries():
    import nba_pra_page1_api_only_v1 as overlay

    calls = []
    now = datetime(2026, 10, 21, 1, 0, tzinfo=timezone.utc)
    schedule = {
        "verification": "VERIFIED",
        "games": [{
            "gameStatus": 1,
            "status": "UPCOMING",
            "game_date_phoenix": "2026-10-21",
            "tip_utc": "2026-10-21T02:00:00Z",
            "away_tricode": "MIA",
            "away_name": "Miami Heat",
            "home_tricode": "ORL",
            "home_name": "Orlando Magic",
        }],
    }
    market = {
        "verification": "VERIFIED",
        "observations": [
            {"provider":"FanDuel","player_name":"Andrew Wiggins","sportsbook":"FanDuel","side":"over","line":19.5,"price":-110,"observed_at_utc":"2026-10-21T00:59:00Z","away_team":"Miami Heat","home_team":"Orlando Magic"},
            {"provider":"FanDuel","player_name":"Andrew Wiggins","sportsbook":"FanDuel","side":"under","line":19.5,"price":-110,"observed_at_utc":"2026-10-21T00:59:00Z","away_team":"Miami Heat","home_team":"Orlando Magic"},
        ],
    }
    context = {
        "verification": "VERIFIED",
        "profiles": {"andrewwiggins": {"player_name":"Andrew Wiggins","team":"MIA","position":"SF","headshot":"x","current_games":[],"prior_games":[{"game_date":"2026-04-10","minutes":34,"points":22,"rebounds":6,"assists":4}]}},
        "provider_health": {"nba_official":{"status":"DEGRADED"},"basketball_reference":{"status":"HEALTHY"}},
        "requested_players": 1,
        "verified_players": 1,
        "fabrication": False,
    }
    injuries = {"verification":"VERIFIED","players":{"andrewwiggins":{"player_name":"Andrew Wiggins","status":"AVAILABLE"}},"fabrication":False}

    snap = overlay.load_page1_snapshot_v2(
        now=now,
        schedule_loader=lambda **_: calls.append("schedule") or schedule,
        api_loader=lambda _day: calls.append("market") or market,
        player_context_loader=lambda _day, _names: calls.append("context") or context,
        injury_loader=lambda _games, **_: calls.append("injury") or injuries,
    )
    assert calls == ["schedule", "market", "context", "injury"]
    assert set(snap["market"]) == {"andrewwiggins"}
    assert snap["profiles"]["andrewwiggins"]["team"] == "MIA"
    assert snap["injury_players"]["andrewwiggins"]["status"] == "AVAILABLE"
    assert snap["sources"]["kyre_sports_api"]["verification"] == "VERIFIED"
    assert snap["sources"]["kyre_player_context"]["verification"] == "VERIFIED"


def test_market_client_has_no_prohibited_book_or_provider_name():
    import nba_pra_market_api_v1 as client
    source = inspect.getsource(client).casefold()
    assert "espn" not in source
    assert "sportsgameodds" not in source
    assert "sgo" not in source
    assert "Fanatics Sportsbook" in client.APPROVED_BOOKS


def test_runless_app_mounts_all_nba_page1_gateway_routes():
    source = open("runless_v2/app.py", encoding="utf-8").read()
    for router_name in (
        "nba_pra_market_router",
        "nba_pra_player_context_router",
        "nba_pra_schedule_router",
        "nba_pra_injury_router",
    ):
        assert source.count(f"include_router({router_name})") >= 2


def test_reference_game_log_parser_reads_data_stat_rows():
    from runless_v2.nba_pra_player_context_v1 import _parse_game_log
    html = '''<table><tr><th data-stat="date_game">2026-04-10</th><td data-stat="mp">34:30</td><td data-stat="pts">22</td><td data-stat="trb">6</td><td data-stat="ast">4</td></tr></table>'''
    rows = _parse_game_log(html)
    assert rows == [{"game_date":"2026-04-10","minutes":34.5,"points":22.0,"rebounds":6.0,"assists":4.0}]


def test_reference_game_log_parser_accepts_current_date_field_name():
    from runless_v2.nba_pra_player_context_v1 import _parse_game_log
    html = '''<table><tr><th data-stat="date">2026-04-10</th><td data-stat="mp">34:30</td><td data-stat="pts">22</td><td data-stat="trb">6</td><td data-stat="ast">4</td></tr></table>'''
    rows = _parse_game_log(html)
    assert rows and rows[0]["game_date"] == "2026-04-10"


def test_reference_profile_meta_accepts_current_team_markup():
    from runless_v2.nba_pra_player_context_v1 import _profile_meta
    html = '''<p><strong>Team</strong>: <a href='/teams/MIA/2027.html'>Miami Heat</a></p><meta property="og:image" content="https://example.com/p.jpg">'''
    team, _position, image = _profile_meta(html, "wiggian01")
    assert team == "MIA"
    assert image == "https://example.com/p.jpg"


def test_schedule_backup_parser_preserves_matchup_and_tip_time():
    from datetime import date, datetime, timezone
    from runless_v2.nba_pra_schedule_v1 import _parse_backup_schedule_html
    html = '''<table><tr><td><a href="/nba/teams/ATL/atlanta-hawks/">Atlanta</a></td><td><a href="/nba/teams/ORL/orlando-magic/">Orlando</a></td><td>7:00 pm</td></tr></table>'''
    rows = _parse_backup_schedule_html(html, date(2026,10,21), datetime(2026,10,21,6,0,tzinfo=timezone.utc))
    assert rows[0]["away_tricode"] == "ATL"
    assert rows[0]["home_tricode"] == "ORL"
    assert rows[0]["tip_utc"] == "2026-10-21T23:00:00Z"
