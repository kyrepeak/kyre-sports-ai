from pathlib import Path
import importlib.util
import math

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / f"{name}.py"
    assert path.exists(), f"missing production module: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_sgo_parser_accepts_only_verified_nba_pra_ou_rows_and_multiple_books():
    data = _load("nba_pra_page1_data_v1")
    event = {
        "eventID": "evt1",
        "teams": {"away": {"names": {"short": "BOS"}}, "home": {"names": {"short": "DET"}}},
        "players": {"p1": {"names": {"display": "Test Guard"}}},
        "odds": {
            "pra-over": {"statID": "points_rebounds_assists", "periodID": "game", "betTypeID": "ou", "sideID": "over", "playerID": "p1", "byBookmaker": {"fanduel": {"available": True, "overUnder": 39.5, "odds": -110}, "draftkings": {"available": True, "overUnder": 39.5, "odds": -105}}},
            "pra-under": {"statID": "points_rebounds_assists", "periodID": "game", "betTypeID": "ou", "sideID": "under", "playerID": "p1", "byBookmaker": {"fanduel": {"available": True, "overUnder": 39.5, "odds": -110}}},
            "points": {"statID": "points", "periodID": "game", "betTypeID": "ou", "sideID": "over", "playerID": "p1", "byBookmaker": {"fanduel": {"available": True, "overUnder": 25.5, "odds": -110}}},
        },
    }
    rows = data.parse_sgo_event_props(event)
    assert len(rows) == 3
    assert {r["sportsbook"] for r in rows} == {"FanDuel", "DraftKings"}
    assert {r["side"] for r in rows} == {"over", "under"}
    assert {r["line"] for r in rows} == {39.5}
    assert all(r["provider"] == "SportsGameOdds" for r in rows)


def test_market_reconciliation_keeps_provider_and_book_provenance():
    data = _load("nba_pra_page1_data_v1")
    sgo = {"observations": [
        {"provider":"SportsGameOdds","player_name":"Test Guard","sportsbook":"FanDuel","side":"over","line":39.5,"price":-110},
        {"provider":"SportsGameOdds","player_name":"Test Guard","sportsbook":"FanDuel","side":"under","line":39.5,"price":-110},
    ]}
    odds = {"observations": [
        {"provider":"Odds-API.io","player_name":"Test Guard","sportsbook":"DraftKings","side":"over","line":40.5,"price":-105},
        {"provider":"Odds-API.io","player_name":"Test Guard","sportsbook":"DraftKings","side":"under","line":40.5,"price":-115},
    ]}
    result = data.reconcile_pra_market(sgo, odds)
    row = result["testguard"]
    assert row["book_count"] == 2
    assert row["providers"] == ["Odds-API.io", "SportsGameOdds"]
    assert set(row["books"]) == {"DraftKings", "FanDuel"}
    assert row["line"] in {39.5, 40.5}


def test_nba_season_end_year_tracks_october_opening_day():
    from datetime import date
    data = _load("nba_pra_page1_data_v1")
    assert data.nba_season_end_year(date(2026, 10, 20)) == 2027
    assert data.nba_season_end_year(date(2027, 4, 1)) == 2027


def test_runtime_overlay_routes_only_nba_pra_and_keeps_upstream_fallback():
    source_path = ROOT / "universal_runtime_v5_loader_nba_pra_page1_v1.py"
    assert source_path.exists(), "missing NBA PRA runtime overlay"
    source = source_path.read_text(encoding="utf-8")
    assert 'route.sport_id == "nba" and route.market_id == "pra"' in source
    assert 'importlib.import_module("nba_pra_page1_v1")' in source
    assert 'return upstream.resolve_destination(route)' in source
    assert 'universal_runtime_v5_loader_nfl_daily_picks_command_v4 as upstream' in source


def test_next_active_slate_selects_today_then_future_without_manual_date_click():
    from datetime import date
    data = _load("nba_pra_page1_data_v1")
    games = [
        {"game_date_phoenix":"2026-10-20","game_key":"a"},
        {"game_date_phoenix":"2026-10-20","game_key":"b"},
        {"game_date_phoenix":"2026-10-21","game_key":"c"},
    ]
    selected, slate = data.select_next_active_slate(games, date(2026,10,20))
    assert selected == "2026-10-20"
    assert [g["game_key"] for g in slate] == ["a","b"]
    selected2, slate2 = data.select_next_active_slate(games, date(2026,10,21))
    assert selected2 == "2026-10-21"
    assert [g["game_key"] for g in slate2] == ["c"]


def test_espn_roster_normalizer_supports_grouped_roster_and_headshots():
    data = _load("nba_pra_page1_data_v1")
    payload = {"athletes":[{"position":"Guard","items":[{"id":"101","displayName":"Test Guard","position":{"abbreviation":"PG"},"headshot":{"href":"https://example.test/p.png"}}]}]}
    rows = data.normalize_espn_roster(payload)
    assert rows == [{"id":"101","name":"Test Guard","position":"PG","headshot":"https://example.test/p.png"}]


def test_espn_gamelog_normalizer_extracts_pra_box_score_fields():
    data = _load("nba_pra_page1_data_v1")
    payload = {"seasonTypes":[{"categories":[{"names":["MIN","FG","PTS","REB","AST"],"events":[{"eventId":"g1","date":"2026-10-10","stats":["36","8-15","25","8","7"]}]}]}]}
    rows = data.normalize_espn_gamelog(payload)
    assert rows == [{"event_id":"g1","date":"2026-10-10","minutes":36.0,"points":25.0,"rebounds":8.0,"assists":7.0}]


