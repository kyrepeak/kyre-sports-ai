from datetime import date
import importlib


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
                    'runners': [
                        {
                            'selectionId': 1,
                            'handicap': 25,
                            'runnerName': 'Jalen Williams 25+',
                            'runnerStatus': 'ACTIVE',
                        }
                    ],
                },
            },
        }
    }


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


def test_fanduel_public_pra_is_primary_and_missing_sgo_key_cannot_block(monkeypatch):
    api = importlib.import_module('runless_v2.nba_pra_market_v1')
    rows = [
        {
            'provider': 'FanDuel',
            'provider_event_id': '35928229',
            'provider_market_id': '734.192200825',
            'provider_player_id': 'Jalen Williams',
            'player_name': 'Jalen Williams',
            'sportsbook': 'FanDuel',
            'side': 'over',
            'line': 28.5,
            'price': -106,
            'observed_at_utc': '2026-10-21T01:25:00Z',
            'away_team': 'Oklahoma City Thunder',
            'home_team': 'San Antonio Spurs',
        },
        {
            'provider': 'FanDuel',
            'provider_event_id': '35928229',
            'provider_market_id': '734.192200825',
            'provider_player_id': 'Jalen Williams',
            'player_name': 'Jalen Williams',
            'sportsbook': 'FanDuel',
            'side': 'under',
            'line': 28.5,
            'price': -114,
            'observed_at_utc': '2026-10-21T01:25:00Z',
            'away_team': 'Oklahoma City Thunder',
            'home_team': 'San Antonio Spurs',
        },
    ]
    calls = {'fanduel': 0, 'sgo': 0}

    def fake_fanduel(day):
        calls['fanduel'] += 1
        assert day == date(2026, 10, 20)
        return rows, 'FANDUEL_OK'

    def fake_sgo(day, key):
        calls['sgo'] += 1
        raise AssertionError('SGO must not run when FanDuel already produced legitimate PRA rows')

    monkeypatch.setattr(api, '_fetch_fanduel_pra_observations', fake_fanduel)
    monkeypatch.setattr(api, '_fetch_sgo_events', fake_sgo)
    payload = api.collect_nba_pra_market(date(2026, 10, 20), None)

    assert calls == {'fanduel': 1, 'sgo': 0}
    assert payload['ready'] is True
    assert payload['diagnostic_state'] == 'OK'
    assert payload['player_count'] == 1
    assert payload['observation_count'] == 2
    assert {row['provider'] for row in payload['observations']} == {'FanDuel'}
    assert payload['projection_weight'] == 0.0
    assert payload['consensus_averaging'] is False
