from datetime import date
import importlib


def _event():
    return {
        'eventID':'okc-sas',
        'teams':{
            'away':{'names':{'long':'Oklahoma City Thunder'}},
            'home':{'names':{'long':'San Antonio Spurs'}},
        },
        'players':{'p1':{'names':{'long':'Shai Gilgeous-Alexander'}}},
        'odds':{
            'o':{'statID':'points+rebounds+assists','sideID':'over','playerID':'p1','periodID':'game','betTypeID':'ou','byBookmaker':{'fanduel':{'available':True,'overUnder':45.5,'odds':'-110','lastUpdatedAt':'2026-10-20T23:00:00Z'}}},
            'u':{'statID':'points+rebounds+assists','sideID':'under','playerID':'p1','periodID':'game','betTypeID':'ou','byBookmaker':{'fanduel':{'available':True,'overUnder':45.5,'odds':'-110','lastUpdatedAt':'2026-10-20T23:00:00Z'}}},
        },
    }


def test_vercel_market_contract_preserves_quote_identity_and_never_echoes_key(monkeypatch):
    api=importlib.import_module('runless_v2.nba_pra_market_v1')
    seen={}
    def fake_fetch(day, api_key):
        seen['day']=day; seen['key']=api_key
        return [_event()], 'OK'
    monkeypatch.setattr(api,'_fetch_sgo_events',fake_fetch)
    payload=api.collect_nba_pra_market(date(2026,10,20),'secret-test-key')
    assert seen=={'day':date(2026,10,20),'key':'secret-test-key'}
    assert payload['service']=='Kyre Sports API — Vercel'
    assert payload['projection_weight']==0.0
    assert payload['consensus_averaging'] is False
    assert payload['player_count']==1
    assert {r['side'] for r in payload['observations']}=={'over','under'}
    assert {r['sportsbook'] for r in payload['observations']}=={'FanDuel'}
    assert {r['provider'] for r in payload['observations']}=={'SportsGameOdds'}
    assert 'secret-test-key' not in repr(payload)


def test_runless_app_keeps_authority_routes_and_mounts_nba_market_route():
    source=open('runless_v2/app.py',encoding='utf-8').read()
    for route in ('/health','/prove','/closeout'):
        assert route in source
    assert 'nba_pra_market_router' in source
    assert 'include_router(nba_pra_market_router)' in source
