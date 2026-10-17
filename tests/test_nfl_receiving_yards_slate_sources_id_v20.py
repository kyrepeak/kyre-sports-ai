from __future__ import annotations

import importlib


def raw_context():
    return {
        'ready': True,
        'data_available': True,
        'official_event_id': '401872997',
        'teams': [
            {
                'official_team_id': '33', 'team_abbreviation': 'BAL', 'team_name': 'Baltimore Ravens',
                'home_away': 'away', 'opponent_official_team_id': '5',
                'players': [
                    {'official_athlete_id': '3916387', 'official_team_id': '33', 'player_name': 'Lamar Jackson', 'position': 'QB'},
                    {'official_athlete_id': '4696882', 'official_team_id': '33', 'player_name': 'Devontez Walker', 'position': 'WR', 'receiving_yards_per_game': 31.0, 'receptions_per_game': 2.0},
                    {'official_athlete_id': '9999999', 'official_team_id': '33', 'player_name': 'Stale Player', 'position': 'WR', 'receiving_yards_per_game': 50.0, 'receptions_per_game': 4.0},
                ],
            },
            {
                'official_team_id': '5', 'team_abbreviation': 'CLE', 'team_name': 'Cleveland Browns',
                'home_away': 'home', 'opponent_official_team_id': '33',
                'players': [
                    {'official_athlete_id': '4832800', 'official_team_id': '5', 'player_name': 'Denzel Boston', 'position': 'WR', 'receiving_yards_per_game': 42.0, 'receptions_per_game': 3.0},
                ],
            },
        ],
    }


def truth():
    return {
        'state': 'live',
        'sources_available': ('ESPN', 'NFLVERSE'),
        'source_count': 2,
        'verified_count': 2,
        'teams': {
            'BAL': {'verified': [
                {'espn_id': '4696882', 'name': 'Devontez Walker', 'position': 'WR', 'team': 'BAL', 'jersey_number': '17', 'gsis_id': '00-003', 'headshot_url': 'https://example.com/walker.png'},
            ]},
            'CLE': {'verified': [
                {'espn_id': '4832800', 'name': 'Denzel Boston', 'position': 'WR', 'team': 'CLE', 'jersey_number': '11', 'gsis_id': '00-004', 'headshot_url': 'https://example.com/boston.png'},
            ]},
        },
    }


def test_multisource_reconciliation_filters_stale_exact_ids_and_enriches_survivors():
    ms = importlib.import_module('nfl_receiving_yards_multisource_v1')
    out = ms.reconcile_exact_id_rosters(raw_context(), truth())
    assert out['ready'] is True
    assert out['data_available'] is True
    assert out['identity_sources'] == ('ESPN', 'NFLVERSE')
    assert out['source_count'] >= 2
    assert out['filtered_stale_player_count'] == 2
    bal = next(team for team in out['teams'] if team['team_abbreviation'] == 'BAL')
    assert [p['official_athlete_id'] for p in bal['players']] == ['4696882']
    assert bal['players'][0]['jersey_number'] == '17'
    assert bal['players'][0]['gsis_id'] == '00-003'
    assert bal['players'][0]['identity_verified'] is True
    assert bal['players'][0]['identity_sources'] == ('ESPN', 'NFLVERSE')


def test_multisource_reconciliation_never_invents_players_absent_from_raw_context():
    ms = importlib.import_module('nfl_receiving_yards_multisource_v1')
    t = truth()
    t['teams']['BAL']['verified'].append({'espn_id': '1234567', 'name': 'New Guy', 'position': 'WR', 'team': 'BAL'})
    out = ms.reconcile_exact_id_rosters(raw_context(), t)
    ids = {p['official_athlete_id'] for team in out['teams'] for p in team['players']}
    assert '1234567' not in ids


def test_source_ownership_is_explicit_and_fanduel_is_display_only():
    ms = importlib.import_module('nfl_receiving_yards_multisource_v1')
    assert ms.SOURCE_OWNERSHIP['event_identity'] == ('ESPN',)
    assert ms.SOURCE_OWNERSHIP['historical_receiving'] == ('ESPN',)
    assert ms.SOURCE_OWNERSHIP['current_roster_identity'] == ('ESPN', 'NFLVERSE')
    assert ms.SOURCE_OWNERSHIP['market_lines'] == ('FANDUEL',)
    assert ms.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_id_cards_show_exact_ids_and_multisource_proof_without_images():
    hub = importlib.import_module('nfl_receiving_yards_hub_v20')
    team = importlib.import_module('nfl_receiving_yards_multisource_v1').reconcile_exact_id_rosters(raw_context(), truth())['teams'][0]
    html = hub._team_id_cards_html_v20(team)
    assert 'ESPN ID 4696882' in html
    assert 'ESPN + NFLVERSE' in html
    assert 'Devontez Walker' in html
    assert '<img' not in html.lower()


def test_v20_is_additive_over_v19_and_keeps_projection_influence_zero():
    hub = importlib.import_module('nfl_receiving_yards_hub_v20')
    assert hub.FROZEN_PRIOR == 'nfl_receiving_yards_hub_v19'
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hub.MULTI_SOURCE_REQUIRED is True
    assert hub.ALL_SLATE_GAMES_REQUIRED is True


def test_universal_router_promotes_receiving_route_to_v20():
    from pathlib import Path
    text = Path('streamlit_memory_lazy_router_universal_nav_v2.py').read_text()
    assert 'RECEIVING_V20_MODULE = "nfl_receiving_yards_hub_v20"' in text
    assert 'module_name = RECEIVING_V20_MODULE' in text
    assert 'module_name = RECEIVING_V19_MODULE' in text
