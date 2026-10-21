from datetime import date, datetime, timezone
import sys, types

NOW=datetime(2026,10,20,22,0,tzinfo=timezone.utc)

def payload(rows): return {"verification":"VERIFIED" if rows else "UNAVAILABLE","observations":rows}
def row(player,book="FanDuel",side="over",line=36.5,price=-110,away="",home="",provider="SportsGameOdds"):
    return {"provider":provider,"player_name":player,"sportsbook":book,"side":side,"line":line,"price":price,
            "observed_at_utc":"2026-10-20T22:20:00Z","away_team":away,"home_team":home}
def schedule():
    return {"verification":"VERIFIED","games":[
        {"gameStatus":1,"gameStatusText":"UPCOMING","tip_utc":"2026-10-20T23:00:00Z","game_date_phoenix":"2026-10-20","away_tricode":"PHI","home_tricode":"NYK"},
        {"gameStatus":1,"gameStatusText":"UPCOMING","tip_utc":"2026-10-21T01:30:00Z","game_date_phoenix":"2026-10-20","away_tricode":"OKC","home_tricode":"SAS"},
    ]}
def kwargs(sgo,odds):
    return dict(now=NOW,schedule_loader=lambda **_:schedule(),sgo_loader=sgo,odds_loader=odds,
                official_profile_loader=lambda day:{},backup_profile_loader=lambda names,day:{},
                injury_loader=lambda games,**kw:{"verification":"VERIFIED","features":[]})

def sgo_event(eid,away,home,pid,name,line):
    def odd(side):
        return {"statID":"points+rebounds+assists","sideID":side,"playerID":pid,"periodID":"game","betTypeID":"ou",
                "byBookmaker":{"fanduel":{"available":True,"overUnder":line,"odds":-110,"lastUpdatedAt":"2026-10-20T22:20:00Z"}}}
    return {"eventID":eid,"updatedAt":"2026-10-20T22:20:00Z","teams":{"away":{"names":{"long":away}},"home":{"names":{"long":home}}},
            "players":{pid:{"names":{"long":name}}},"odds":{f"{eid}-o":odd("over"),f"{eid}-u":odd("under")}}

class Response:
    def __init__(self,p): self.p=p
    def raise_for_status(self): pass
    def json(self): return self.p

def test_existing_streamlit_session_sportsbook_keys_are_reused(monkeypatch):
    import nba_pra_page1_data_v2 as common
    monkeypatch.setitem(sys.modules,"streamlit",types.SimpleNamespace(session_state={"ks_sportsgameodds_key":"sgo-session-key","ks_odds_api_key":"odds-session-key"},secrets={}))
    for key in ("SPORTSGAMEODDS_API_KEY","SGO_API_KEY","ODDS_API_IO_KEY","ODDS_API_KEY"): monkeypatch.delenv(key,raising=False)
    assert common._connected_secret("SPORTSGAMEODDS_API_KEY")=="sgo-session-key"
    assert common._connected_secret("SGO_API_KEY")=="sgo-session-key"
    assert common._connected_secret("ODDS_API_IO_KEY")=="odds-session-key"
    assert common._connected_secret("ODDS_API_KEY")=="odds-session-key"

def test_legacy_sportsgameodds_secret_alias_is_reused(monkeypatch):
    import nba_pra_page1_data_v2 as common
    monkeypatch.setitem(sys.modules,"streamlit",types.SimpleNamespace(session_state={},secrets={"SPORTSGAMEODDS_KEY":"legacy-production-key"}))
    for key in ("SPORTSGAMEODDS_API_KEY","SPORTSGAMEODDS_KEY","SGO_API_KEY"): monkeypatch.delenv(key,raising=False)
    assert common._connected_secret("SPORTSGAMEODDS_API_KEY")=="legacy-production-key"

def test_sgo_uses_full_phoenix_slate_day_so_both_night_games_are_covered():
    from nba_pra_page1_data_v2 import _load_sgo_primary
    captured={}
    events=[sgo_event("phi-nyk","Philadelphia 76ers","New York Knicks","brunson","Jalen Brunson",36.5),
            sgo_event("okc-sas","Oklahoma City Thunder","San Antonio Spurs","sga","Shai Gilgeous-Alexander",42.5)]
    def get(url,**kw): captured.update(kw["params"]); return Response({"data":events})
    result=_load_sgo_primary(date(2026,10,20),request_get=get,secret_getter=lambda _:"key")
    assert captured["startsAfter"]=="2026-10-20T07:00:00Z"
    assert captured["startsBefore"]=="2026-10-21T07:00:00Z"
    assert {"Jalen Brunson","Shai Gilgeous-Alexander"}<={r["player_name"] for r in result["observations"]}
    assert len({(r["away_team"],r["home_team"]) for r in result["observations"]})==2

def test_snapshot_skips_secondary_when_primary_covers_both_games():
    from nba_pra_page1_data_v2 import load_page1_snapshot_v2
    calls=[]
    rows=[row("Jalen Brunson",side=s,line=36.5,away="Philadelphia 76ers",home="New York Knicks") for s in ("over","under")]
    rows += [row("Shai Gilgeous-Alexander",side=s,line=42.5,away="Oklahoma City Thunder",home="San Antonio Spurs") for s in ("over","under")]
    snap=load_page1_snapshot_v2(**kwargs(lambda d:calls.append("sgo") or payload(rows),lambda d:calls.append("odds") or payload([])))
    assert calls==["sgo"]
    assert {"jalenbrunson","shaigilgeousalexander"}<=set(snap["market"])

def test_snapshot_does_not_use_application_side_fallback_when_gateway_has_no_market():
    from nba_pra_page1_api_only_v1 import load_page1_snapshot_v2
    calls=[]
    snap=load_page1_snapshot_v2(
        now=NOW,
        schedule_loader=lambda **_: schedule(),
        api_loader=lambda day: calls.append("api") or payload([]),
        player_context_loader=lambda day,names: calls.append("context") or {"verification":"DATA_UNAVAILABLE","profiles":{},"fabrication":False},
        injury_loader=lambda games,**kw: calls.append("injury") or {"verification":"UNAVAILABLE","players":{},"fabrication":False},
        odds_loader=lambda day: (_ for _ in ()).throw(AssertionError("direct fallback must not run")),
    )
    assert calls == ["api"]
    assert snap["market"] == {}

def test_snapshot_uses_secondary_only_to_fill_missing_matchup():
    from nba_pra_page1_data_v2 import load_page1_snapshot_v2
    calls=[]
    primary=[row("Jalen Brunson",side=s,away="Philadelphia 76ers",home="New York Knicks") for s in ("over","under")]
    fallback=[row("Shai Gilgeous-Alexander","DraftKings",s,42.5,-110,"Oklahoma City Thunder","San Antonio Spurs","Odds-API.io") for s in ("over","under")]
    snap=load_page1_snapshot_v2(**kwargs(lambda d:calls.append("sgo") or payload(primary),lambda d:calls.append("odds") or payload(fallback)))
    assert calls==["sgo","odds"]
    assert {"jalenbrunson","shaigilgeousalexander"}<=set(snap["market"])
