from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import PropObservation
from cfb_player_props_page2_roster_v1 import Page2Player


def _player():
    return Page2Player(CanonicalPlayerIdentity('p1','t1','Roman Gagliano','QB','Middle Tennessee','MTSU'))


def _context():
    return {'state':'ready','slate_date':'2026-10-20','official_game_id':'g1','away_team_id':'t1','away_team':'Middle Tennessee','home_team_id':'t2','home_team':'FIU','player':_player(),'official_player_id':'p1','market_key':'passing_yards','handoff_line':199.5}


def _obs():
    base=dict(official_game_id='g1',canonical_player_id='p1',player_name='Roman Gagliano',official_team_id='t1',market_key='passing_yards',sportsbook='FanDuel',observed_at_utc='2026-10-20T18:50:00Z',provider='fanduel',provider_event_id='fd1',provider_player_id='fdp1',provider_market_id='fdm1',identity_verified=True)
    return [PropObservation(**base,side='over',line=202.5,price=-114),PropObservation(**base,side='under',line=202.5,price=-114)]


def _history():
    return [{'event_id':f'e{i}','completed':True,'market_key':'passing_yards','value':value,'game_date':f'2026-10-{20-i:02d}'} for i,value in enumerate([240,180,210,199,260,150,230,220],1)]


def _wire(monkeypatch,a, observations=None, matchup_label='FAVORABLE'):
    monkeypatch.setattr(a.page2_market,'load_game_prop_observations',lambda context,players:list(_obs() if observations is None else observations))
    monkeypatch.setattr(a.page3_history,'load_page3_history',lambda player,market_key,season:list(_history()))
    monkeypatch.setattr(a.page2_matchup,'load_game_matchup_context',lambda context:{'ready':True})
    monkeypatch.setattr(a.page2_matchup,'grade_player_matchup',lambda player,market_key,ctx:{'label':matchup_label,'detail':'verified matchup','model_influence':0.0})
    monkeypatch.setattr(a.page2_availability,'load_game_availability',lambda context,players:{'p1':{'state':'AVAILABLE','source':'verified'}})


def test_analysis_packet_reuses_current_market_and_frozen_projection(monkeypatch):
    import cfb_player_props_page3_analysis_v1 as a
    _wire(monkeypatch,a)
    out=a.build_page3_analysis(_context(),selected_line=205.5,season=2026)
    assert out['state']=='ready'
    assert out['market']['consensus_line']==202.5
    assert out['market']['book_count']==1
    assert out['line_lab']['line']==205.5
    assert out['projection']['sample_count']==8
    assert out['sportsbook_projection_influence']==0.0
    assert out['opponent_team_id']=='t2'
    assert out['availability']['state']=='AVAILABLE'
    assert out['matchup']['model_influence']==0.0
    assert out['movement']['available'] is False
    assert out['reasoning']['why']
    assert out['reasoning']['bull_case']
    assert out['reasoning']['bear_case']
    assert out['quality']['model_sample_count']==8
    assert out['quality']['verified_book_count']==1


def test_market_disappears_without_silent_substitution(monkeypatch):
    import cfb_player_props_page3_analysis_v1 as a
    _wire(monkeypatch,a,observations=[])
    out=a.build_page3_analysis(_context(),selected_line=None,season=2026)
    assert out['state']=='market_unavailable'
    assert out['market']['book_count']==0
    assert out['market']['consensus_line'] is None
    assert out['line_lab']['line']==199.5
    assert out['market_key']=='passing_yards'


def test_matchup_label_never_changes_projection_or_probability(monkeypatch):
    import cfb_player_props_page3_analysis_v1 as a
    _wire(monkeypatch,a,matchup_label='FAVORABLE')
    one=a.build_page3_analysis(_context(),selected_line=202.5,season=2026)
    _wire(monkeypatch,a,matchup_label='TOUGH')
    two=a.build_page3_analysis(_context(),selected_line=202.5,season=2026)
    assert one['projection']==two['projection']
    assert one['line_lab']==two['line_lab']
    assert one['matchup']['label'] != two['matchup']['label']


def test_reasoning_does_not_invent_movement_or_confidence():
    import cfb_player_props_page3_analysis_v1 as a
    reasoning=a.build_reasoning({'projection':210.0,'line':202.5,'margin':7.5,'model_ready':True},{'last5':{'average':205.0,'sample_size':5}},{'label':'CHECK'},{'state':'UNVERIFIED'},{'available':False})
    text=' '.join(reasoning['why']+[reasoning['bull_case'],reasoning['bear_case']]).lower()
    assert 'opening' not in text
    assert 'high confidence' not in text
    assert 'medium confidence' not in text
    assert 'low confidence' not in text
