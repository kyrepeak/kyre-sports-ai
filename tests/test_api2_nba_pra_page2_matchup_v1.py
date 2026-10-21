from __future__ import annotations


def test_grade_rank_boundaries_are_explicit_and_one_is_toughest():
    from nba_pra_page2_matchup_v1 import grade_rank, RANK_SEMANTICS
    assert grade_rank(1) == 'TOUGH'
    assert grade_rank(10) == 'TOUGH'
    assert grade_rank(11) == 'MEDIUM'
    assert grade_rank(21) == 'MEDIUM'
    assert grade_rank(22) == 'FAVORABLE'
    assert grade_rank(30) == 'FAVORABLE'
    assert grade_rank(None) == 'UNAVAILABLE'
    assert grade_rank(31) == 'UNAVAILABLE'
    assert '1 = toughest' in RANK_SEMANTICS


def test_matchup_summary_keeps_components_separate_and_builds_transparent_pra_composite():
    from nba_pra_page2_matchup_v1 import build_matchup_summary
    rows = {
        'points': {'rank': 4, 'value': 104.2},
        'rebounds': {'rank': 17, 'value': 44.0},
        'assists': {'rank': 28, 'value': 29.1},
        'source': 'Kyre Sports API — CBS Sports',
        'evidence_period': '2026-27 PRESEASON BASELINE',
    }
    out = build_matchup_summary(rows)
    assert out['points']['rank'] == 4 and out['points']['grade'] == 'TOUGH'
    assert out['rebounds']['rank'] == 17 and out['rebounds']['grade'] == 'MEDIUM'
    assert out['assists']['rank'] == 28 and out['assists']['grade'] == 'FAVORABLE'
    assert out['pra_rank'] == 16
    assert out['matchup_grade'] == 'MEDIUM'
    assert out['pra_method'] == 'mean of verified PTS/REB/AST opponent ranks'
    assert out['evidence_period'] == '2026-27 PRESEASON BASELINE'
    assert 'projection' not in out


def test_missing_component_fails_closed_for_pra_grade():
    from nba_pra_page2_matchup_v1 import build_matchup_summary
    out = build_matchup_summary({'points': {'rank': 4}, 'rebounds': {'rank': 17}})
    assert out['pra_rank'] is None
    assert out['matchup_grade'] == 'UNAVAILABLE'


def test_cbs_table_parser_maps_team_and_metric_without_guessing():
    from runless_v2.nba_pra_matchup_v1 import parse_cbs_opponent_table
    html = '''<table><thead><tr><th>Team</th><th>GP</th><th>PPG</th></tr></thead>
    <tbody><tr><td>Golden St.</td><td>5</td><td>101.2</td></tr>
    <tr><td>L.A. Lakers</td><td>4</td><td>109.8</td></tr></tbody></table>'''
    rows = parse_cbs_opponent_table(html, metric='PPG')
    assert rows == [
        {'team': 'GSW', 'games_played': 5, 'value': 101.2},
        {'team': 'LAL', 'games_played': 4, 'value': 109.8},
    ]


def test_rank_rows_lower_allowed_is_tougher():
    from runless_v2.nba_pra_matchup_v1 import rank_rows
    ranked = rank_rows([
        {'team':'LAL','games_played':4,'value':109.8},
        {'team':'GSW','games_played':5,'value':101.2},
        {'team':'BOS','games_played':4,'value':105.0},
    ])
    assert ranked['GSW']['rank'] == 1
    assert ranked['BOS']['rank'] == 2
    assert ranked['LAL']['rank'] == 3

def test_cbs_parser_accepts_live_header_tooltip_text():
    from runless_v2.nba_pra_matchup_v1 import parse_cbs_opponent_table
    html = '''<table><thead><tr><th>Team</th><th>GP Games played</th><th>PPG Points Per Game</th></tr></thead>
    <tbody><tr><td>L.A. Lakers</td><td>4</td><td>109.8</td></tr></tbody></table>'''
    assert parse_cbs_opponent_table(html, metric='PPG') == [
        {'team':'LAL','games_played':4,'value':109.8}
    ]

def test_page2_matchup_client_calls_kyre_gateway_only():
    from nba_pra_page2_matchup_api_v1 import load_kyre_sports_api_nba_pra_matchup
    calls=[]
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'verification':'VERIFIED','opponent':'LAL'}
    def post(url, **kwargs):
        calls.append((url,kwargs)); return Response()
    result=load_kyre_sports_api_nba_pra_matchup('LAL',request_post=post,base_url='https://kyre.example')
    assert result['verification']=='VERIFIED'
    assert calls[0][0]=='https://kyre.example/api/v1/nba/pra/matchup'
    assert calls[0][1]['json']=={'opponent':'LAL'}


def test_runless_app_registers_matchup_router():
    from pathlib import Path
    text=Path('runless_v2/app.py').read_text()
    assert 'nba_pra_matchup_router' in text
    assert 'include_router(nba_pra_matchup_router)' in text
