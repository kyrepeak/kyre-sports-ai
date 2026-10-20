from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_page2_roster_v1 import Page2Player
from cfb_player_props_page2_handoff_v1 import SESSION_HANDOFF_KEY


def _player(pid='p1'):
    return Page2Player(CanonicalPlayerIdentity(pid, 't1', 'Roman Gagliano', 'QB', 'Middle Tennessee', 'MTSU'))


def _game():
    return {
        'state':'ready','slate_date':'2026-10-20','official_game_id':'g1',
        'away_team_id':'t1','away_team':'Middle Tennessee','away_abbr':'MTSU',
        'home_team_id':'t2','home_team':'FIU','home_abbr':'FIU','generation':7,
    }


def _wire(monkeypatch, page3, players=None):
    monkeypatch.setattr(page3.page2_context, 'resolve_page2_context', lambda session, query: _game())
    monkeypatch.setattr(page3.page2_roster, 'load_offensive_roster', lambda context: {'away': list(players or [_player()]), 'home': []})


def test_resolve_page3_context_exact_player_market(monkeypatch):
    import cfb_player_props_page3_context_v1 as page3
    _wire(monkeypatch, page3)
    handoff={'official_game_id':'g1','official_player_id':'p1','player_name':'Roman Gagliano','official_team_id':'t1','market_key':'passing_yards','consensus_line':202.5,'generation':7}
    session={SESSION_HANDOFF_KEY: handoff,'date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'passing_yards'}
    query={'date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'passing_yards'}
    out=page3.resolve_page3_context(session,query)
    assert out['state']=='ready'
    assert out['official_game_id']=='g1'
    assert out['official_player_id']=='p1'
    assert out['market_key']=='passing_yards'
    assert out['player'].canonical_name=='Roman Gagliano'
    assert out['handoff_line']==202.5


def test_stale_player_does_not_substitute_another_player(monkeypatch):
    import cfb_player_props_page3_context_v1 as page3
    _wire(monkeypatch, page3, [_player('p1')])
    out=page3.resolve_page3_context({'date':'2026-10-20','game_id':'g1','player_id':'missing','prop':'passing_yards'}, {})
    assert out['state']=='player_unavailable'
    assert out.get('player') is None


def test_unsupported_market_fails_closed(monkeypatch):
    import cfb_player_props_page3_context_v1 as page3
    _wire(monkeypatch, page3)
    out=page3.resolve_page3_context({'date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'made_up_market'}, {})
    assert out['state']=='invalid'
    assert out.get('market_key') is None


def test_back_clears_page3_only_and_preserves_exact_game():
    import cfb_player_props_page3_context_v1 as page3
    slider_key='cfbpp3_slider_g1:p1:passing_yards'
    session={'sport':'cfb','market':'player-props','date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'passing_yards','cfbpp3_line':205.5,'cfbpp3_line_identity':'g1:p1:passing_yards',slider_key:205.5}
    query=dict(session)
    page3.clear_page3_selection(session,query)
    for mapping in (session,query):
        assert mapping['sport']=='cfb' and mapping['market']=='player-props'
        assert mapping['date']=='2026-10-20' and mapping['game_id']=='g1'
        assert 'player_id' not in mapping and 'prop' not in mapping
        assert 'cfbpp3_line' not in mapping and 'cfbpp3_line_identity' not in mapping
        assert slider_key not in mapping


def test_switch_market_preserves_game_and_player_and_resets_line_state():
    import cfb_player_props_page3_context_v1 as page3
    slider_key='cfbpp3_slider_g1:p1:passing_yards'
    session={'date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'passing_yards','cfbpp3_line':202.5,'cfbpp3_line_identity':'old',slider_key:222.5}
    query={'date':'2026-10-20','game_id':'g1','player_id':'p1','prop':'passing_yards',slider_key:222.5}
    assert page3.switch_page3_market(session,query,'rushing_yards') is True
    assert session['game_id']=='g1' and session['player_id']=='p1' and session['prop']=='rushing_yards'
    assert query['game_id']=='g1' and query['player_id']=='p1' and query['prop']=='rushing_yards'
    assert 'cfbpp3_line' not in session and 'cfbpp3_line_identity' not in session
    assert slider_key not in session and slider_key not in query
    before=dict(session)
    assert page3.switch_page3_market(session,query,'not_real') is False
    assert session==before
