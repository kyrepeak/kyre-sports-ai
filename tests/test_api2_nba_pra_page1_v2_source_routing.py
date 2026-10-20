from datetime import date, datetime, timezone
import sys, types

from nba_pra_page1_sources_v2 import (
    APPROVED_PRA_BOOKS,
    build_sportsbook_board,
    normalize_nba_stats_league_gamelog,
    route_player_profiles,
    select_featured_quote,
)


def payload(rows):
    return {"verification": "VERIFIED", "observations": rows}


def test_conflicting_sportsbook_lines_stay_separate_and_never_average():
    board = build_sportsbook_board(
        payload([
            {"provider":"SportsGameOdds","player_name":"Devin Booker","sportsbook":"FanDuel","side":"over","line":38.5,"price":-110,"observed_at_utc":"2026-10-20T20:30:00Z"},
            {"provider":"SportsGameOdds","player_name":"Devin Booker","sportsbook":"FanDuel","side":"under","line":38.5,"price":-110,"observed_at_utc":"2026-10-20T20:30:00Z"},
        ]),
        payload([
            {"provider":"Odds-API.io","player_name":"Devin Booker","sportsbook":"DraftKings","side":"over","line":39.5,"price":-105,"observed_at_utc":"2026-10-20T20:31:00Z"},
            {"provider":"Odds-API.io","player_name":"Devin Booker","sportsbook":"DraftKings","side":"under","line":39.5,"price":-115,"observed_at_utc":"2026-10-20T20:31:00Z"},
        ]),
    )
    entry = board["devinbooker"]
    assert [(q["sportsbook"], q["line"]) for q in entry["quotes"]] == [("FanDuel", 38.5), ("DraftKings", 39.5)]
    assert 39.0 not in [q["line"] for q in entry["quotes"]]
    assert select_featured_quote(entry)["sportsbook"] == "FanDuel"
    assert select_featured_quote(entry)["line"] == 38.5


def test_quote_keeps_source_prices_timestamp_and_filters_unapproved_books():
    board = build_sportsbook_board(payload([
        {"provider":"Odds-API.io","player_name":"Kevin Durant","sportsbook":"BetMGM","side":"over","line":36.5,"price":-108,"observed_at_utc":"2026-10-20T20:32:00Z"},
        {"provider":"Odds-API.io","player_name":"Kevin Durant","sportsbook":"BetMGM","side":"under","line":36.5,"price":-112,"observed_at_utc":"2026-10-20T20:32:00Z"},
        {"provider":"Odds-API.io","player_name":"Kevin Durant","sportsbook":"Pinnacle","side":"over","line":37.0,"price":-101,"observed_at_utc":"2026-10-20T20:32:00Z"},
    ]))
    quote = board["kevindurant"]["quotes"][0]
    assert quote == {"sportsbook":"BetMGM","line":36.5,"over_price":-108,"under_price":-112,"provider":"Odds-API.io","observed_at_utc":"2026-10-20T20:32:00Z"}
    assert "Pinnacle" not in APPROVED_PRA_BOOKS


def test_nba_stats_normalizer_and_official_first_backup_only_for_missing():
    raw = {"resultSets":[{"headers":["PLAYER_ID","PLAYER_NAME","TEAM_ABBREVIATION","GAME_DATE","MIN","PTS","REB","AST"],"rowSet":[[201,"Devin Booker","PHX","OCT 18, 2026",36,31,5,7]]}]}
    official = normalize_nba_stats_league_gamelog(raw)
    assert official["devinbooker"]["games"][0]["points"] == 31
    assert official["devinbooker"]["games"][0]["minutes"] == 36
    calls = []
    def official_loader(_):
        calls.append("official")
        return {"devinbooker":{"player_name":"Devin Booker","team":"PHX","stats_source":"NBA Stats"}}
    def backup(names, _):
        calls.append(("backup", tuple(names)))
        return {"kevindurant":{"player_name":"Kevin Durant","team":"PHX","stats_source":"ESPN backup"}}
    routed = route_player_profiles(["Devin Booker","Kevin Durant"], date(2026,10,20), official_loader=official_loader, backup_loader=backup)
    assert routed["devinbooker"]["stats_source"] == "NBA Stats"
    assert routed["kevindurant"]["stats_source"] == "ESPN backup"
    assert calls == ["official", ("backup", ("Kevin Durant",))]


def test_snapshot_routes_only_upcoming_slate_and_skips_calls_when_empty():
    from nba_pra_page1_data_v2 import load_page1_snapshot_v2
    now = datetime(2026,10,20,20,45,tzinfo=timezone.utc)
    calls=[]
    schedule={"verification":"VERIFIED","games":[
        {"gameStatus":2,"gameStatusText":"Live","tip_utc":"2026-10-20T20:00:00Z","game_date_phoenix":"2026-10-20","away_tricode":"BOS","home_tricode":"NYK"},
        {"gameStatus":1,"gameStatusText":"Scheduled","tip_utc":"2026-10-21T02:00:00Z","game_date_phoenix":"2026-10-20","away_tricode":"LAL","home_tricode":"PHX"},
    ]}
    def sgo(day):
        calls.append(("sgo",str(day)))
        return payload([
            {"provider":"SportsGameOdds","player_name":"Devin Booker","sportsbook":"FanDuel","side":"over","line":38.5,"price":-110,"observed_at_utc":"2026-10-20T20:30:00Z"},
            {"provider":"SportsGameOdds","player_name":"Devin Booker","sportsbook":"FanDuel","side":"under","line":38.5,"price":-110,"observed_at_utc":"2026-10-20T20:30:00Z"},
        ])
    snap=load_page1_snapshot_v2(
        now=now,
        schedule_loader=lambda **_: schedule,
        sgo_loader=sgo,
        odds_loader=lambda day: payload([]),
        official_profile_loader=lambda day: {"devinbooker":{"player_name":"Devin Booker","team":"PHX","current_games":[],"prior_games":[],"stats_source":"NBA Stats"}},
        backup_profile_loader=lambda names,day: calls.append(("backup",tuple(names))) or {},
        injury_loader=lambda games,**kwargs: calls.append(("injury",tuple(g["away_tricode"] for g in games))) or {"verification":"VERIFIED","features":[]},
    )
    assert [g["away_tricode"] for g in snap["games"]] == ["LAL"]
    assert snap["market"]["devinbooker"]["featured_quote"]["sportsbook"] == "FanDuel"
    assert ("injury", ("LAL",)) in calls
    assert not any(call[0] == "backup" for call in calls)
    calls.clear()
    empty=load_page1_snapshot_v2(
        now=now,
        schedule_loader=lambda **_: {"verification":"VERIFIED","games":[schedule["games"][0]]},
        sgo_loader=lambda day: calls.append(("sgo",day)),
        odds_loader=lambda day: calls.append(("odds",day)),
        official_profile_loader=lambda day: calls.append(("official",day)),
        backup_profile_loader=lambda names,day: calls.append(("backup",names,day)),
        injury_loader=lambda games,**kwargs: calls.append(("injury",games)),
    )
    assert empty["games"] == [] and empty["market"] == {} and calls == []


def test_default_injury_route_is_nba_official_only_not_legacy_espn_fallback(monkeypatch):
    import nba_pra_page1_data_v2 as data_v2
    calls=[]
    fake=types.SimpleNamespace()
    def fetch_official(games, now_utc):
        calls.append(("official",len(games)))
        return ([{"game_key":"LAL@PHX","team_tricode":"PHX","player_name":"Devin Booker","status":"Available"}], {"available":True,"reported_at_utc":now_utc})
    def build(games, **kwargs):
        calls.append(("build",kwargs["official_available"],kwargs["espn_available"],tuple(kwargs["espn_rows"])))
        return {"verification":"VERIFIED","features":[]}
    fake._fetch_official_rows=fetch_official
    fake.build_game_injury_features=build
    monkeypatch.setitem(sys.modules,"nba_spread_injury_availability_v1",fake)
    now=datetime(2026,10,20,20,45,tzinfo=timezone.utc)
    assert data_v2._default_injury_loader([{"game_key":"LAL@PHX"}], now_utc=now)["verification"] == "VERIFIED"
    assert calls == [("official",1),("build",True,False,())]
