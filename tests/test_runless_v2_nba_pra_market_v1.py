from datetime import date
import importlib
import inspect


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


def _fanduel_event_page_fixture():
    return {
        'attachments': {
            'events': {
                '35928229': {
                    'eventId': 35928229,
                    'name': 'Oklahoma City Thunder @ San Antonio Spurs',
                    'openDate': '2026-10-21T01:40:00Z',
                    'competitionId': 10547864,
                }
            },
            'markets': {
                'pra': {
                    'marketId': '734.192200825',
                    'eventId': 35928229,
                    'marketName': 'Jalen Williams - Pts + Reb + Ast',
                    'marketType': 'PLAYER_C_TOTAL_POINTS_+_REB_+_AST',
                    'marketStatus': 'OPEN',
                    'inPlay': False,
                    'runners': [
                        {
                            'selectionId': 43310613,
                            'handicap': 28.5,
                            'runnerName': 'Jalen Williams Over',
                            'result': {'type': 'OVER'},
                            'runnerStatus': 'ACTIVE',
                            'teamAbbr': 'OKC',
                            'winRunnerOdds': {'americanDisplayOdds': {'americanOddsInt': -106}},
                        },
                        {
                            'selectionId': 43310614,
                            'handicap': 28.5,
                            'runnerName': 'Jalen Williams Under',
                            'result': {'type': 'UNDER'},
                            'runnerStatus': 'ACTIVE',
                            'teamAbbr': 'OKC',
                            'winRunnerOdds': {'americanDisplayOdds': {'americanOddsInt': -114}},
                        },
                    ],
                },
                'alt': {
                    'marketId': '734.alt',
                    'eventId': 35928229,
                    'marketName': 'Jalen Williams - Alt Pts + Reb + Ast',
                    'marketType': 'PLAYER_C_ALT_TOTAL_PTS_+_REB_+_AST',
                    'marketStatus': 'OPEN',
                    'inPlay': False,
                    'runners': [{'selectionId': 1, 'handicap': 25, 'runnerName': 'Jalen Williams 25+', 'runnerStatus': 'ACTIVE'}],
                },
            },
        }
    }


def test_vercel_market_contract_preserves_quote_identity_without_provider_credential(monkeypatch):
    api = importlib.import_module('runless_v2.nba_pra_market_v1')
    rows = api._parse_fanduel_pra_page(
        _fanduel_event_page_fixture(),
        captured_at_utc='2026-10-21T01:25:00Z',
    )
    seen = []
    def fake_fetch(day):
        seen.append(day)
        return rows, 'FANDUEL_OK'
    monkeypatch.setattr(api, '_fetch_fanduel_pra_observations', fake_fetch)
    payload = api.collect_nba_pra_market(date(2026, 10, 20))
    assert seen == [date(2026, 10, 20)]
    assert payload['service'] == 'Kyre Sports API — Vercel'
    assert payload['projection_weight'] == 0.0
    assert payload['consensus_averaging'] is False
    assert payload['player_count'] == 1
    assert {r['side'] for r in payload['observations']} == {'over','under'}
    assert {r['sportsbook'] for r in payload['observations']} == {'FanDuel'}
    assert {r['provider'] for r in payload['observations']} == {'FanDuel'}

def test_market_module_has_no_prohibited_provider_fallback_symbols():
    api = importlib.import_module('runless_v2.nba_pra_market_v1')
    source = inspect.getsource(api).casefold()
    assert 'sportsgameodds' not in source
    assert '_fetch_sgo_events' not in source
    assert 'sgo_base' not in source

def test_runless_app_keeps_authority_routes_and_mounts_nba_market_route():
    source=open('runless_v2/app.py',encoding='utf-8').read()
    for route in ('/health','/prove','/closeout'):
        assert route in source
    assert 'nba_pra_market_router' in source
    assert 'include_router(nba_pra_market_router)' in source


def test_fanduel_public_pra_parser_preserves_exact_standard_over_under_market():
    api = importlib.import_module('runless_v2.nba_pra_market_v1')
    rows = api._parse_fanduel_pra_page(
        _fanduel_event_page_fixture(),
        captured_at_utc='2026-10-21T01:25:00Z',
    )
    assert len(rows) == 2
    assert {row['side'] for row in rows} == {'over', 'under'}
    assert {row['line'] for row in rows} == {28.5}
    assert {row['price'] for row in rows} == {-106, -114}
    assert {row['player_name'] for row in rows} == {'Jalen Williams'}
    assert {row['provider'] for row in rows} == {'FanDuel'}
    assert {row['sportsbook'] for row in rows} == {'FanDuel'}
    assert {row['away_team'] for row in rows} == {'Oklahoma City Thunder'}
    assert {row['home_team'] for row in rows} == {'San Antonio Spurs'}
    assert all(row['provider_market_id'] == '734.192200825' for row in rows)
    assert all(row['observed_at_utc'] == '2026-10-21T01:25:00Z' for row in rows)


def test_fanduel_public_pra_is_the_only_active_market_transport(monkeypatch):
    api = importlib.import_module('runless_v2.nba_pra_market_v1')
    rows = api._parse_fanduel_pra_page(
        _fanduel_event_page_fixture(),
        captured_at_utc='2026-10-21T01:25:00Z',
    )
    calls = []
    def fake_fanduel(day):
        calls.append(day)
        return rows, 'FANDUEL_OK'
    monkeypatch.setattr(api, '_fetch_fanduel_pra_observations', fake_fanduel)
    payload = api.collect_nba_pra_market(date(2026, 10, 20))
    assert calls == [date(2026, 10, 20)]
    assert payload['ready'] is True
    assert payload['diagnostic_state'] == 'OK'
    assert payload['player_count'] == 1
    assert payload['observation_count'] == 2
    assert {row['provider'] for row in payload['observations']} == {'FanDuel'}
    assert payload['projection_weight'] == 0.0
    assert payload['consensus_averaging'] is False
