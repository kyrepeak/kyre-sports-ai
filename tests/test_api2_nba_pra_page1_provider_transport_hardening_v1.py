from datetime import date, datetime, timezone


def _game():
    return {'away_tricode':'OKC','home_tricode':'SAS','away_name':'Oklahoma City Thunder','home_name':'San Antonio Spurs','status':'UPCOMING','gameStatus':1,'tip_utc':'2026-10-21T01:30:00Z','game_date_phoenix':'2026-10-20'}

def _rows(source='SportsGameOdds'):
    base={'provider':source,'provider_event_id':'okc-sas','provider_player_id':'p1','player_name':'Shai Gilgeous-Alexander','sportsbook':'FanDuel','line':45.5,'observed_at_utc':'2026-10-20T23:00:00Z','away_team':'Oklahoma City Thunder','home_team':'San Antonio Spurs'}
    return [{**base,'side':'over','price':-110},{**base,'side':'under','price':-110}]

def test_client_uses_vercel_kyre_api_without_echoing_key():
    import nba_pra_market_api_v1 as client
    seen={}
    class R:
        def raise_for_status(self): pass
        def json(self): return {'service':'Kyre Sports API — Vercel','ready':True,'observations':_rows(),'projection_weight':0.0,'consensus_averaging':False}
    def fake_post(url, **kwargs):
        seen['url']=url; seen['json']=dict(kwargs['json']); return R()
    out=client.load_kyre_sports_api_pra_observations(date(2026,10,20),api_key='secret-test-key',request_post=fake_post)
    assert seen['url']=='https://kyre-runless-proof.vercel.app/api/v1/nba/pra/market'
    assert seen['json']=={'date':'2026-10-20','sportsgameodds_api_key':'secret-test-key'}
    assert len(out['observations'])==2
    assert out['sportsbook_projection_influence']==0.0
    assert 'secret-test-key' not in repr(out)

def test_page1_api_first_suppresses_direct_calls_when_complete():
    import nba_pra_page1_data_v2 as data
    calls={'sgo':0,'odds':0}
    def api(day): return {'source':'Kyre Sports API','verification':'VERIFIED','observations':_rows()}
    def sgo(day): calls['sgo']+=1; return {'observations':[]}
    def odds(day): calls['odds']+=1; return {'observations':[]}
    snap=data.load_page1_snapshot_v2(
        now=datetime(2026,10,20,23,1,tzinfo=timezone.utc),
        schedule_loader=lambda **k:{'verification':'VERIFIED','games':[_game()]},
        api_loader=api,sgo_loader=sgo,odds_loader=odds,
        official_profile_loader=lambda d:{'shaigilgeousalexander':{'player_name':'Shai Gilgeous-Alexander','team':'OKC','current_games':[],'prior_games':[]}},
        backup_profile_loader=lambda *a:{},injury_loader=lambda *a,**k:{'verification':'VERIFIED','features':[]},
    )
    assert snap['market']
    assert len(snap['market'])==1
    assert calls=={'sgo':0,'odds':0}

def test_page1_api_unavailable_uses_direct_primary_then_one_secondary_if_needed():
    import nba_pra_page1_data_v2 as data
    calls={'sgo':0,'odds':0}
    def api(day): return {'source':'Kyre Sports API','verification':'UNAVAILABLE','observations':[]}
    def sgo(day): calls['sgo']+=1; return {'source':'SportsGameOdds','verification':'UNAVAILABLE','observations':[]}
    def odds(day): calls['odds']+=1; return {'source':'Odds-API.io','verification':'VERIFIED','observations':_rows('Odds-API.io')}
    snap=data.load_page1_snapshot_v2(
        now=datetime(2026,10,20,23,1,tzinfo=timezone.utc),
        schedule_loader=lambda **k:{'verification':'VERIFIED','games':[_game()]},
        api_loader=api,sgo_loader=sgo,odds_loader=odds,
        official_profile_loader=lambda d:{'shaigilgeousalexander':{'player_name':'Shai Gilgeous-Alexander','team':'OKC','current_games':[],'prior_games':[]}},
        backup_profile_loader=lambda *a:{},injury_loader=lambda *a,**k:{'verification':'VERIFIED','features':[]},
    )
    assert snap['market']
    assert calls=={'sgo':1,'odds':1}
    quote=next(iter(snap['market'].values()))['featured_quote']
    assert quote['sportsbook']=='FanDuel'
    assert quote['line']==45.5


def test_page1_default_api_path_forwards_connected_sgo_key(monkeypatch):
    import nba_pra_page1_data_v2 as data
    seen={}
    monkeypatch.setattr(data,'_connected_secret',lambda name: 'connected-sgo-key' if name in {'SPORTSGAMEODDS_API_KEY','SGO_API_KEY'} else None)
    def api(day, *, api_key=None, **kwargs):
        seen['day']=day; seen['api_key']=api_key
        return {'source':'Kyre Sports API — Vercel','verification':'VERIFIED','observations':_rows()}
    monkeypatch.setattr(data,'load_kyre_sports_api_pra_observations',api)
    snap=data.load_page1_snapshot_v2(
        now=datetime(2026,10,20,23,1,tzinfo=timezone.utc),
        schedule_loader=lambda **k:{'verification':'VERIFIED','games':[_game()]},
        sgo_loader=lambda day: (_ for _ in ()).throw(AssertionError('direct SGO should be skipped')),
        odds_loader=lambda day: (_ for _ in ()).throw(AssertionError('secondary should be skipped')),
        official_profile_loader=lambda d:{'shaigilgeousalexander':{'player_name':'Shai Gilgeous-Alexander','team':'OKC','current_games':[],'prior_games':[]}},
        backup_profile_loader=lambda names,d:{}, injury_loader=lambda *a,**k:{},
    )
    assert seen['api_key']=='connected-sgo-key'
    assert len(snap['market'])==1


def test_unrelated_api_event_does_not_cover_upcoming_game_and_fallback_fills_it():
    import nba_pra_page1_data_v2 as data
    stale=[]
    for side in ('over','under'):
        stale.append({
            'provider':'SportsGameOdds','provider_event_id':'phi-nyk','provider_player_id':'p2',
            'player_name':'Jalen Brunson','sportsbook':'FanDuel','side':side,'line':41.5,
            'price':-110,'observed_at_utc':'2026-10-20T23:00:00Z',
            'away_team':'Philadelphia 76ers','home_team':'New York Knicks',
        })
    calls={'sgo':0,'odds':0}
    def api(day):
        return {'source':'Kyre Sports API — Vercel','verification':'VERIFIED','observations':stale}
    def sgo(day):
        calls['sgo']+=1
        return {'source':'SportsGameOdds','verification':'VERIFIED','observations':_rows()}
    def odds(day):
        calls['odds']+=1
        return {'source':'Odds-API.io','verification':'UNAVAILABLE','observations':[]}
    snap=data.load_page1_snapshot_v2(
        now=datetime(2026,10,20,23,1,tzinfo=timezone.utc),
        schedule_loader=lambda **k:{'verification':'VERIFIED','games':[_game()]},
        api_loader=api,sgo_loader=sgo,odds_loader=odds,
        official_profile_loader=lambda d:{'shaigilgeousalexander':{'player_name':'Shai Gilgeous-Alexander','team':'OKC','current_games':[],'prior_games':[]}},
        backup_profile_loader=lambda names,d:{}, injury_loader=lambda *a,**k:{},
    )
    assert calls['sgo']==1
    assert calls['odds']==0
    assert set(snap['market'])=={'shaigilgeousalexander'}
    assert all(entry['player_name']!='Jalen Brunson' for entry in snap['market'].values())


def test_odds_api_fallback_preserves_event_and_team_identity():
    from nba_pra_page1_sources_v2 import load_approved_odds_api_pra_observations
    class R:
        def __init__(self,payload): self._payload=payload
        def raise_for_status(self): pass
        def json(self): return self._payload
    event={
        'id':'okc-sas','startTime':'2026-10-21T01:30:00Z',
        'awayTeam':'Oklahoma City Thunder','homeTeam':'San Antonio Spurs',
    }
    odds={'bookmakers':{'DraftKings':[{
        'name':'Player Props','updatedAt':'2026-10-20T23:00:00Z','odds':[
            {'label':'Shai Gilgeous-Alexander Points + Rebounds + Assists','hdp':45.5,'over':1.91,'under':1.91}
        ]
    }]}}
    def get(url, **kwargs):
        return R([event] if url.endswith('/events') else odds)
    out=load_approved_odds_api_pra_observations(
        date(2026,10,20),request_get=get,secret_getter=lambda name:'odds-key'
    )
    assert out['verification']=='VERIFIED'
    assert out['observations']
    assert {r['provider_event_id'] for r in out['observations']}=={'okc-sas'}
    assert {r['away_team'] for r in out['observations']}=={'Oklahoma City Thunder'}
    assert {r['home_team'] for r in out['observations']}=={'San Antonio Spurs'}


def test_client_calls_kyre_api_without_sgo_key_instead_of_short_circuiting():
    import nba_pra_market_api_v1 as client
    seen = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                'service': 'Kyre Sports API — Vercel',
                'ready': False,
                'observations': [],
                'projection_weight': 0.0,
                'consensus_averaging': False,
                'diagnostic_state': 'NO_AVAILABLE_PRA_PROVIDER',
            }

    def fake_post(url, **kwargs):
        seen['url'] = url
        seen['json'] = dict(kwargs['json'])
        return R()

    out = client.load_kyre_sports_api_pra_observations(
        date(2026, 10, 20), api_key=None, request_post=fake_post
    )
    assert seen['url'] == 'https://kyre-runless-proof.vercel.app/api/v1/nba/pra/market'
    assert seen['json'] == {'date': '2026-10-20'}
    assert out['diagnostic_state'] == 'NO_AVAILABLE_PRA_PROVIDER'


def test_vercel_market_route_accepts_missing_sgo_key_and_skips_sgo(monkeypatch):
    import runless_v2.nba_pra_market_v1 as api

    def forbidden(*args, **kwargs):
        raise AssertionError('SGO must not be called when its optional credential is absent')

    monkeypatch.setattr(api, '_fetch_sgo_events', forbidden)
    request = api.NbaPraMarketRequest(date=date(2026, 10, 20))
    payload = api.market(request)
    assert payload['service'] == 'Kyre Sports API — Vercel'
    assert payload['observations'] == []
    assert payload['diagnostic_state'] == 'NO_AVAILABLE_PRA_PROVIDER'
    assert payload['projection_weight'] == 0.0
    assert payload['consensus_averaging'] is False
