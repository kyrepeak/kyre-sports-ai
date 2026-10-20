from cfb_player_props_identity_v1 import CanonicalPlayerIdentity


def _rows():
    return [
        {'event_id':'e1','completed':True,'market_key':'passing_yards','value':240.0,'game_date':'2026-10-15','opponent_team_id':'opp','pass_attempts':31,'completions':20},
        {'event_id':'e2','completed':True,'market_key':'passing_yards','value':180.0,'game_date':'2026-10-08','opponent_team_id':'x','pass_attempts':27,'completions':17},
        {'event_id':'e3','completed':True,'market_key':'passing_yards','value':210.0,'game_date':'2026-10-01','opponent_team_id':'x','pass_attempts':29,'completions':19},
        {'event_id':'e4','completed':True,'market_key':'passing_yards','value':199.0,'game_date':'2026-09-24','opponent_team_id':'x','pass_attempts':30,'completions':18},
        {'event_id':'e5','completed':True,'market_key':'passing_yards','value':260.0,'game_date':'2026-09-17','opponent_team_id':'x','pass_attempts':35,'completions':24},
        {'event_id':'e6','completed':True,'market_key':'passing_yards','value':150.0,'game_date':'2026-09-10','opponent_team_id':'x'},
        {'event_id':'e7','completed':True,'market_key':'passing_yards','value':230.0,'game_date':'2026-09-03','opponent_team_id':'x'},
        {'event_id':'e8','completed':True,'market_key':'passing_yards','value':220.0,'game_date':'2026-08-28','opponent_team_id':'x'},
        {'event_id':'e9','completed':True,'market_key':'passing_yards','value':205.0,'game_date':'2026-08-21','opponent_team_id':'x'},
    ]


def test_history_view_has_explicit_l5_l8_season_samples_and_hit_rates():
    import cfb_player_props_page3_history_v1 as h
    view=h.build_history_view(_rows(), 202.5)
    assert view['last5']['sample_size']==5
    assert view['last8']['sample_size']==8
    assert view['season']['sample_size']==9
    assert view['last5']['hits']==3
    assert view['last8']['hits']==5
    assert view['season']['hits']==6
    assert view['chart'][0]['event_id']=='e1'
    assert all(row['comparison_line']==202.5 for row in view['chart'])


def test_missing_values_are_excluded_not_coerced_to_zero():
    import cfb_player_props_page3_history_v1 as h
    rows=[{'event_id':'bad','completed':True,'value':None},{'event_id':'ok','completed':True,'value':11.0}]
    view=h.build_history_view(rows,10.5)
    assert view['season']['sample_size']==1
    assert view['season']['values']==(11.0,)


def test_opportunity_evidence_uses_only_explicit_market_specific_fields():
    import cfb_player_props_page3_history_v1 as h
    evidence=h.build_opportunity_evidence(_rows(),'passing_yards')
    assert evidence['available'] is True
    assert evidence['metrics']['pass_attempts']['sample_size']==5
    assert evidence['metrics']['completions']['sample_size']==5
    assert 'snap_share' not in evidence['metrics']
    missing=h.build_opportunity_evidence([{'value':40.0}],'receiving_yards')
    assert missing['available'] is False
    assert missing['metrics']=={}


def test_prior_opponent_history_requires_exact_verified_opponent_identity():
    import cfb_player_props_page3_history_v1 as h
    exact=h.build_prior_opponent_history(_rows(),'opp')
    assert exact['available'] is True
    assert exact['sample_size']==1
    assert exact['rows'][0]['event_id']=='e1'
    assert h.build_prior_opponent_history(_rows(),'not-there')['available'] is False
    assert h.build_prior_opponent_history([{'event_id':'e1','opponent_name':'FIU','value':10}], 'opp')['available'] is False


def test_load_page3_history_enriches_real_gamelog_auxiliary_fields(monkeypatch):
    import cfb_player_props_page3_history_v1 as h
    player=CanonicalPlayerIdentity('p1','t1','Roman Gagliano','QB','Middle Tennessee','MTSU')
    base=[{'event_id':'e1','completed':True,'market_key':'passing_yards','value':240.0,'game_date':'2026-10-15','source':'ESPN CFB athlete gamelog'}]
    payload={
        'events':[{'eventId':'e1','date':'2026-10-15T20:00:00Z','opponent':{'id':'opp'}}],
        'categories':[
            {'name':'passing','labels':['C/ATT','YDS'],'events':[{'eventId':'e1','completed':True,'stats':['20/31','240']}]},
            {'name':'rushing','labels':['CAR','YDS'],'events':[{'eventId':'e1','completed':True,'stats':['8','44']}]},
            {'name':'receiving','labels':['REC','YDS','TGTS'],'events':[{'eventId':'e1','completed':True,'stats':['3','28','5']}]},
        ],
    }
    monkeypatch.setattr(h.frozen_history,'load_verified_player_history',lambda p,m,season:list(base))
    monkeypatch.setattr(h.frozen_history,'_fetch_gamelog',lambda athlete_id,season:payload)
    rows=h.load_page3_history(player,'passing_yards',season=2026)
    assert rows[0]['completions']==20
    assert rows[0]['pass_attempts']==31
    assert rows[0]['carries']==8
    assert rows[0]['receptions']==3
    assert rows[0]['targets']==5
    assert rows[0]['opponent_team_id']=='opp'


def test_load_verified_history_delegates_to_frozen_owner(monkeypatch):
    import cfb_player_props_page3_history_v1 as h
    player=CanonicalPlayerIdentity('p1','t1','Roman Gagliano','QB','Middle Tennessee','MTSU')
    seen=[]
    monkeypatch.setattr(h.frozen_history,'load_verified_player_history',lambda p,m,season: seen.append((p,m,season)) or _rows())
    monkeypatch.setattr(h.frozen_history,'_fetch_gamelog',lambda athlete_id,season:{})
    rows=h.load_page3_history(player,'passing_yards',season=2026)
    assert len(rows)==9
    assert seen==[(player,'passing_yards',2026)]
