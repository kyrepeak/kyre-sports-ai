from datetime import datetime, timezone
from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / 'sports_api/api/cfb_moneyline_page1_v1.py'
COLLECTOR = ROOT / 'sports_api/collectors/cfb_fanduel_moneyline_v1.py'
HEALTH = ROOT / 'sports_api/api/health.py'


def test_moneyline_api_and_market_router_exist_without_forbidden_providers():
    assert API.exists()
    assert COLLECTOR.exists()
    text = (API.read_text() + COLLECTOR.read_text()).casefold()
    assert 'espn' not in text
    assert 'sportsgameodds' not in text
    assert 'sgo' not in text
    assert 'espn bet' not in text
    assert '/api/v1/cfb/moneyline' in API.read_text()


def test_fanduel_parser_preserves_exact_book_prices_without_averaging():
    m = importlib.import_module('sports_api.collectors.cfb_fanduel_moneyline_v1')
    payload = {
        'attachments': {
            'events': {
                'e1': {'eventId': 'e1', 'name': 'James Madison @ Appalachian State', 'openDate': '2026-10-22T23:00:00Z'},
            },
            'markets': {
                'm1': {
                    'marketId': 'm1', 'eventId': 'e1', 'marketName': 'Moneyline', 'marketStatus': 'OPEN', 'inPlay': False,
                    'runners': [
                        {'runnerName': 'James Madison', 'runnerStatus': 'ACTIVE', 'result': {'type': 'AWAY'}, 'winRunnerOdds': {'americanDisplayOdds': {'americanOddsInt': -430}}},
                        {'runnerName': 'Appalachian State', 'runnerStatus': 'ACTIVE', 'result': {'type': 'HOME'}, 'winRunnerOdds': {'americanDisplayOdds': {'americanOddsInt': 330}}},
                    ],
                }
            },
        }
    }
    rows = m.normalize_fanduel_moneylines(payload, observed_at_utc=datetime(2026,10,22,2,0,tzinfo=timezone.utc))
    assert rows == [{
        'sportsbook': 'FanDuel', 'market': 'moneyline', 'provider_event_id': 'e1', 'provider_market_id': 'm1',
        'away_team': 'James Madison', 'home_team': 'Appalachian State', 'away_price': -430, 'home_price': 330,
        'observed_at_utc': '2026-10-22T02:00:00+00:00', 'line_status': 'open',
    }]
    assert 'average' not in COLLECTOR.read_text().casefold()
    assert 'consensus' not in COLLECTOR.read_text().casefold()


def test_strict_ncaa_to_fanduel_identity_supports_verified_aliases_only():
    m = importlib.import_module('sports_api.collectors.cfb_fanduel_moneyline_v1')
    game = {'game_id':'n1','away_team':'James Madison','home_team':'App State','kickoff_iso':'2026-10-22T19:00:00-04:00'}
    row = {'sportsbook':'FanDuel','market':'moneyline','provider_event_id':'e1','provider_market_id':'m1','away_team':'James Madison','home_team':'Appalachian State','away_price':-430,'home_price':330,'observed_at_utc':'2026-10-22T02:00:00+00:00','line_status':'open'}
    matched = m.match_moneylines_to_ncaa_games([game], [row])
    assert matched['n1'][0]['away_price'] == -430
    assert matched['n1'][0]['home_price'] == 330
    assert m.match_moneylines_to_ncaa_games([game], [{**row, 'away_team':'Liberty'}]) == {}


def test_page_payload_uses_ncaa_identity_and_existing_model_with_null_safe_market(monkeypatch):
    api = importlib.import_module('sports_api.api.cfb_moneyline_page1_v1')
    games = [{'game_id':'n1','away_team':'James Madison','home_team':'App State','kickoff_iso':'2026-10-22T23:00:00+00:00','identity_verified':True,'date_matches_query':True,'schedule_source':'NCAA current FBS scoreboard GraphQL'}]
    monkeypatch.setattr(api, '_load_ncaa_games', lambda day: games)
    monkeypatch.setattr(api, 'collect_market_rows', lambda: [{'sportsbook':'FanDuel','market':'moneyline','provider_event_id':'e1','provider_market_id':'m1','away_team':'James Madison','home_team':'Appalachian State','away_price':-430,'home_price':330,'observed_at_utc':'2026-10-22T02:00:00+00:00','line_status':'open'}])
    monkeypatch.setattr(api, 'match_moneylines_to_ncaa_games', lambda gs, rows: {'n1': rows})
    monkeypatch.setattr(api.team_data, 'load_matchup_team_data', lambda game, day: ({'away':{'team':'James Madison'},'home':{'team':'App State'}},{'stats_source':'NCAA.com FBS team stats'}))
    monkeypatch.setattr(api.raw_model, 'project_matchup', lambda game, away, home: {'ready':True,'confidence':'MEDIUM'})
    monkeypatch.setattr(api.final_model, 'synthesize', lambda game, away, home, raw: {'ready':True,'winner_team':'James Madison','winner_side':'away','winner_probability_final':0.60,'away_fair_moneyline':-150,'home_fair_moneyline':130,'reliability':0.94,'feature_coverage':0.75,'model_grade':'C','model_tier':'LEAN'})
    payload = api.build_page1_payload(game_date='2026-10-22', game_id='n1', now_provider=lambda: datetime(2026,10,22,1,0,tzinfo=timezone.utc))
    assert payload['service'] == 'Kyre Sports API'
    assert payload['selected_date'] == '2026-10-22'
    assert payload['games'][0]['market_quotes'][0]['sportsbook'] == 'FanDuel'
    assert payload['games'][0]['market_quotes'][0]['away_price'] == -430
    assert payload['analysis']['final']['winner_probability_final'] == 0.60
    assert payload['routing']['application_gateway'] == 'Kyre Sports API'
    assert payload['routing']['sportsbook_projection_weight'] == 0.0
    assert payload['routing']['consensus_averaging'] is False
    assert payload['routing']['forbidden_providers'] == []


def test_health_registers_moneyline_page1_router():
    src = HEALTH.read_text()
    assert 'cfb_moneyline_page1_v1 import router as cfb_moneyline_page1_router' in src
    assert 'router.routes.extend(cfb_moneyline_page1_router.routes)' in src


def test_ncaa_stats_only_repair_uses_published_games_and_never_guesses_history():
    api = importlib.import_module('sports_api.api.cfb_moneyline_page1_v1')
    profile = {
        'team':'James Madison',
        'team_slug':'james-madison',
        'conference':'sun-belt',
        'official_stats': {
            'scoring_offense': {'value_numeric':42.9,'headers':['Rank','Team','G','Pts','PPG'],'row':['3','James Madison','7','300','42.9']},
            'scoring_defense': {'value_numeric':16.0,'headers':['Rank','Team','G','Pts','Avg'],'row':['-','James Madison','7','112','16.0']},
            'turnover_margin': {'value_numeric':1.0,'headers':['Rank','Team','G','Avg'],'row':['10','James Madison','7','1.00']},
        },
        'data_quality': {'grade':'CHECK'},
    }
    repaired, did_repair = api._repair_ncaa_stats_profile('away', {'away_team':'James Madison','away_team_slug':'james-madison','away_conference':'sun-belt'}, profile)
    assert did_repair is True
    assert repaired['record'] == {'games':7}
    assert repaired['record_text'] == '7 GAME SAMPLE • W-L UNAVAILABLE'
    assert repaired['ppg'] == 42.9
    assert repaired['points_allowed_pg'] == 16.0
    assert repaired['recent_ppg'] is None
    assert repaired['sos_opponent_win_pct'] is None
    assert repaired['data_source'].startswith('NCAA.com official team stats + NCAA official event record')
    assert repaired['data_quality']['grade'] != 'CHECK'
