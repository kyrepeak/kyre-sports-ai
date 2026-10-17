from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    assert find_spec('nfl_receiving_yards_hub_v18') is not None, 'Receiving Yards V18 cleanup owner must exist'
    return import_module('nfl_receiving_yards_hub_v18')


def _player(pid, *, name, ypg=0.0, rpg=0.0, position='WR', team='34'):
    return {
        'official_athlete_id': str(pid),
        'official_team_id': str(team),
        'official_event_id': '401872996',
        'player_name': name,
        'position': position,
        'receiving_yards_per_game': ypg,
        'receptions_per_game': rpg,
        'sample_games': 6,
    }


def test_relevance_filter_keeps_market_or_projection_players_and_caps_each_team(monkeypatch):
    m = _mod()
    context = {
        'ready': True,
        'data_available': True,
        'official_event_id': '401872996',
        'teams': [
            {
                'official_team_id': '34',
                'opponent_official_team_id': '30',
                'players': [
                    _player('1', name='Market One', ypg=70, rpg=5),
                    _player('2', name='Projection Two', ypg=60, rpg=4),
                    _player('3', name='Usage Three', ypg=50, rpg=3),
                    _player('4', name='Usage Four', ypg=40, rpg=3),
                    _player('5', name='Usage Five', ypg=30, rpg=2),
                    _player('6', name='Depth Six', ypg=2, rpg=.2),
                ],
            },
            {
                'official_team_id': '30',
                'opponent_official_team_id': '34',
                'players': [_player('7', name='Other Team', ypg=55, rpg=4, team='30')],
            },
        ],
    }
    event_market = {
        'ready': True,
        'market_available': True,
        'props': [{'official_athlete_id': '1', 'official_team_id': '34', 'line': 64.5}],
    }

    def fake_projection(*, official_event_id, team, player):
        return {'ready': player['official_athlete_id'] in {'2', '7'}, 'projection_yards': 45.0}

    monkeypatch.setattr(m.projection_engine, 'build_player_projection', fake_projection)
    filtered = m._filter_context_for_relevant_players(context, event_market, max_per_team=5)
    first = filtered['teams'][0]['players']
    second = filtered['teams'][1]['players']
    assert [p['official_athlete_id'] for p in first] == ['1', '2', '3', '4', '5']
    assert [p['official_athlete_id'] for p in second] == ['7']
    assert filtered['relevance_filter_applied'] is True
    assert filtered['relevant_player_count'] == 6


def test_relevance_filter_drops_depth_filler_when_three_meaningful_options_exist(monkeypatch):
    m = _mod()
    team = {
        'official_team_id': '34',
        'opponent_official_team_id': '30',
        'players': [
            _player('1', name='A', ypg=80, rpg=6),
            _player('2', name='B', ypg=55, rpg=4),
            _player('3', name='C', ypg=32, rpg=2),
            _player('4', name='D', ypg=3, rpg=.2),
            _player('5', name='E', ypg=1, rpg=.1),
        ],
    }
    context = {'ready': True, 'data_available': True, 'official_event_id': '401872996', 'teams': [team]}
    market = {'ready': True, 'market_available': True, 'props': [
        {'official_athlete_id': '1', 'official_team_id': '34', 'line': 69.5},
        {'official_athlete_id': '2', 'official_team_id': '34', 'line': 48.5},
    ]}
    monkeypatch.setattr(m.projection_engine, 'build_player_projection', lambda **kw: {'ready': kw['player']['official_athlete_id'] == '3', 'projection_yards': 31.0})
    filtered = m._filter_context_for_relevant_players(context, market, max_per_team=5)
    assert [p['official_athlete_id'] for p in filtered['teams'][0]['players']] == ['1', '2', '3']


def test_top_matchup_options_use_exact_event_ids_and_phoenix_labels():
    m = _mod()
    games = pd.DataFrame([
        {'game_id': '401872996', 'away_abbr': 'HOU', 'home_abbr': 'JAX', 'tip_et': '9:30 AM ET', 'game_date': '2026-10-18'},
        {'game_id': '401872997', 'away_abbr': 'TEN', 'home_abbr': 'IND', 'tip_et': '1:00 PM ET', 'game_date': '2026-10-18'},
    ])
    labels = m._matchup_labels(games)
    assert list(labels) == ['401872996', '401872997']
    assert labels['401872996'].startswith('HOU @ JAX')
    assert 'MST' in labels['401872996'] or 'Phoenix' in labels['401872996']


def test_compact_schedule_renders_one_top_matchup_selector_and_no_big_metric_grid(monkeypatch):
    m = _mod()
    games = pd.DataFrame([
        {'game_id': '401872996', 'away_abbr': 'HOU', 'home_abbr': 'JAX', 'tip_et': '9:30 AM ET', 'game_date': '2026-10-18'},
        {'game_id': '401872997', 'away_abbr': 'TEN', 'home_abbr': 'IND', 'tip_et': '1:00 PM ET', 'game_date': '2026-10-18'},
    ])
    session = {}
    calls = {'selectbox': [], 'metric': 0, 'markdown': []}
    fake = SimpleNamespace(
        session_state=session,
        selectbox=lambda label, **kwargs: calls['selectbox'].append((label, kwargs)) or kwargs['options'][0],
        markdown=lambda body, **kwargs: calls['markdown'].append(str(body)),
        caption=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        info=lambda *a, **k: None,
        columns=lambda *a, **k: (_ for _ in ()).throw(AssertionError('large metric grid must not render')),
    )
    monkeypatch.setattr(m, 'st', fake)
    selected = m._render_compact_schedule(games, '2026-10-18', {'request_ok': True})
    assert selected == '401872996'
    assert calls['selectbox'][0][0] == m.TOP_MATCHUP_LABEL
    assert session[m.EVENT_KEY] == '401872996'
    assert not any('Games' in body and 'Upcoming' in body for body in calls['markdown'])


def test_clean_markdown_suppresses_build_banners_and_step_language(monkeypatch):
    m = _mod()
    seen = []
    delegate = lambda body, *a, **k: seen.append(str(body))
    clean = m._make_clean_markdown(delegate)
    assert clean('<div class="krecv2-banner">✅ Step 7 explains the frozen Step 6 projection</div>', unsafe_allow_html=True) is None
    assert clean('<div class="krecv-section"><h3>🎯 Step 2 • Receiver Player Cards</h3></div>', unsafe_allow_html=True) is None
    clean('<div>Real player analysis</div>', unsafe_allow_html=True)
    assert seen == ['<div>Real player analysis</div>']


def test_market_lineup_is_restricted_to_filtered_context(monkeypatch):
    m = _mod()
    context = {'teams': [{'official_team_id': '34', 'players': [_player('1', name='Keep')]}]}
    market = {'ready': True, 'market_available': True, 'props': [
        {'official_athlete_id': '1', 'official_team_id': '34', 'player_name': 'Keep', 'line': 55.5},
        {'official_athlete_id': '2', 'official_team_id': '34', 'player_name': 'Drop', 'line': 12.5},
    ]}
    captured = {}
    def fake_original(ctx, reduced):
        captured['ids'] = [x['official_athlete_id'] for x in reduced['props']]
        return '<section>Full Standard Lineup</section>'
    monkeypatch.setattr(m, '_ORIGINAL_LINEUP_HTML_V8', fake_original)
    html = m._relevant_lineup_board_html(context, market)
    assert captured['ids'] == ['1']
    assert 'Key Receiving Yards Lines' in html
    assert 'Full Standard Lineup' not in html


def test_universal_nav_v2_routes_receiving_v17_import_to_v18_and_hides_router_debug():
    source = (ROOT / 'streamlit_memory_lazy_router_universal_nav_v2.py').read_text(encoding='utf-8')
    assert 'nfl_receiving_yards_hub_v17' in source
    assert 'nfl_receiving_yards_hub_v18' in source
    assert 'KYRE STREAMLIT MEMORY LAZY ROUTER V1' in source
    assert 'receiving-yards' in source


def test_v18_never_changes_projection_or_sportsbook_influence_contract():
    m = _mod()
    assert m.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    source = (ROOT / 'nfl_receiving_yards_hub_v18.py').read_text(encoding='utf-8')
    assert 'build_player_projection' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'prior.render_nfl_receiving_yards_hub()' in source
