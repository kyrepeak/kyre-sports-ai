from datetime import date, datetime, timezone
from pathlib import Path


def _game():
    return {
        'source': 'CBS Sports',
        'source_game_id': 'g1',
        'game_key': 'ATL@ORL:2026-10-21',
        'away_tricode': 'ATL',
        'away_name': 'Atlanta Hawks',
        'home_tricode': 'ORL',
        'home_name': 'Orlando Magic',
        'tip_utc': '2026-10-22T00:00:00Z',
        'tip_phoenix': '5:00 PM MST',
        'game_date_phoenix': '2026-10-21',
        'status': 'UPCOMING',
    }


def _market():
    return {
        'source': 'Kyre Sports API',
        'verification': 'VERIFIED',
        'diagnostic_state': 'OK',
        'fabrication': False,
        'observations': [
            {'provider':'FanDuel','provider_event_id':'g1','provider_player_id':'p1','player_name':'Trae Young','sportsbook':'FanDuel','side':'over','line':39.5,'price':-110,'observed_at_utc':'2026-10-21T04:00:00Z','away_team':'Atlanta Hawks','home_team':'Orlando Magic'},
            {'provider':'FanDuel','provider_event_id':'g1','provider_player_id':'p1','player_name':'Trae Young','sportsbook':'FanDuel','side':'under','line':39.5,'price':-110,'observed_at_utc':'2026-10-21T04:00:00Z','away_team':'Atlanta Hawks','home_team':'Orlando Magic'},
        ],
    }


def _enrichment():
    return {
        'schema_version':'KYRE_NBA_ENRICHMENT_V1','data_state':'VERIFIED','fabrication':False,
        'requested_players':1,'verified_players':1,
        'provider_health':{'cbs_sports':{'status':'HEALTHY','attempted':True}},
        'profiles':{
            'traeyoung':{
                'kyre_player_id':'KYRE-NBA-TEST','player_name':'Trae Young','team':'ATL','position':'PG',
                'provider_ids':{'cbs_sports':'x'},'headshot':'https://example.test/trae.png',
                'current_games':[],'prior_games':[{'game_date':'2026-04-01','minutes':36,'points':30,'rebounds':4,'assists':10}],
                'stats_source':'CBS Sports','data_state':'VERIFIED',
            }
        },
    }


def test_frontend_context_client_contains_only_kyre_api_transport():
    source = Path('nba_pra_context_api_v1.py').read_text(encoding='utf-8').casefold()
    assert 'kyre-runless-proof.vercel.app' in source
    for forbidden in ('espn.com','cbssports.com','stats.nba.com','sportsgameodds','sgo'):
        assert forbidden not in source


def test_active_page1_default_context_does_not_execute_legacy_direct_provider_paths(monkeypatch):
    import nba_pra_page1_api_only_v1 as page

    def forbidden(*_args, **_kwargs):
        raise AssertionError('legacy direct provider path must not execute')

    monkeypatch.setattr(page._core, '_default_schedule_loader', forbidden)
    monkeypatch.setattr(page._core, '_default_injury_loader', forbidden)
    monkeypatch.setattr(page._legacy, '_recover_quorum_schedule', forbidden)

    context = {
        'schema_version':'KYRE_NBA_CONTEXT_V1','verification':'VERIFIED','fabrication':False,
        'schedule':{'verification':'VERIFIED','diagnostic_state':'OK','games':[_game()]},
        'injuries':{'verification':'UNAVAILABLE','diagnostic_state':'NO_VERIFIED_REPORT','features':[]},
        'provider_health':{'cbs_sports':{'status':'HEALTHY','attempted':True}},
    }
    snap = page.load_page1_snapshot_v2(
        now=datetime(2026,10,21,4,5,tzinfo=timezone.utc),
        context_loader=lambda now_utc: context,
        api_loader=lambda day:_market(),
        enrichment_loader=lambda day,names:_enrichment(),
    )
    assert snap['market']['traeyoung']['featured_quote']['line'] == 39.5
    assert snap['profiles']['traeyoung']['kyre_player_id'] == 'KYRE-NBA-TEST'
    assert snap['sources']['nba_context']['verification'] == 'VERIFIED'


def test_server_context_falls_from_official_schedule_to_cbs_without_forbidden_sources():
    from runless_v2.nba_pra_context_v1 import build_nba_pra_context

    calls=[]
    def official(_now):
        calls.append('official')
        raise TimeoutError('official unavailable')
    def cbs(_now):
        calls.append('cbs')
        return [_game()]
    def injury(_games, _now):
        calls.append('injury')
        return {'verification':'UNAVAILABLE','diagnostic_state':'NO_VERIFIED_REPORT','features':[]}

    payload = build_nba_pra_context(
        datetime(2026,10,21,4,5,tzinfo=timezone.utc),
        official_schedule_loader=official,
        cbs_schedule_loader=cbs,
        official_injury_loader=injury,
        env={},
    )
    assert payload['schedule']['verification'] == 'VERIFIED'
    assert payload['schedule']['games'][0]['game_key'] == 'ATL@ORL:2026-10-21'
    assert payload['provider_health']['nba_official_schedule']['status'] == 'DEGRADED'
    assert payload['provider_health']['sportradar_schedule']['status'] == 'UNAVAILABLE'
    assert payload['provider_health']['sportsdataio_schedule']['status'] == 'UNAVAILABLE'
    assert payload['provider_health']['cbs_sports_schedule']['status'] == 'HEALTHY'
    assert calls == ['official','cbs','injury']
    assert 'espn' not in repr(payload).casefold()
    assert 'sgo' not in repr(payload).casefold()
