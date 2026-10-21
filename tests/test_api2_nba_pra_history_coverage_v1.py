from datetime import date

import runless_v2.nba_pra_player_context_v1 as ctx


def _daily_html(players):
    rows=[]
    for i,name in enumerate(players, start=1):
        slug=''.join(ch for ch in name.lower() if ch.isalpha())[:8] + '01'
        rows.append(f'''<tr>
          <td data-stat="player"><a href="/players/a/{slug}.html">{name}</a></td>
          <td data-stat="team_id">T{i:02d}</td>
          <td data-stat="mp">3{i%10}:30</td>
          <td data-stat="pts">{10+i}</td>
          <td data-stat="trb">{3+i%5}</td>
          <td data-stat="ast">{2+i%7}</td>
        </tr>''')
    return '<table><tbody>' + ''.join(rows) + '</tbody></table>'


def test_daily_leaders_parser_builds_verified_game_rows_for_many_players():
    names=[f'Player {i}' for i in range(1,13)]
    parsed=ctx._parse_reference_daily_leaders(_daily_html(names), '2026-04-12')
    assert len(parsed) == 12
    row=parsed[ctx._norm('Player 1')]
    assert row['player_name'] == 'Player 1'
    assert row['game']['game_date'] == '2026-04-12'
    assert row['game']['minutes'] == 31.5
    assert row['game']['points'] == 11.0
    assert row['game']['rebounds'] == 4.0
    assert row['game']['assists'] == 3.0
    assert row['provider_ids']['basketball_reference']


def test_bulk_history_loader_is_not_limited_to_eight_players():
    names=[f'Player {i}' for i in range(1,13)]
    pages={
        '2026-04-12': _daily_html(names),
        '2026-04-10': _daily_html(names),
    }
    result=ctx._reference_bulk_history_profiles(
        date(2026,10,21), names,
        current_game_dates=[], prior_game_dates=['2026-04-12','2026-04-10'],
        daily_page_loader=lambda day: pages[day],
        target_games=2,
    )
    assert result['status'] == 'HEALTHY'
    assert len(result['profiles']) == 12
    assert all(len(row['prior_games']) == 2 for row in result['profiles'].values())
    assert 'RESOLVED_12_OF_12' in result['diagnostic_state']


def test_context_router_uses_bulk_history_for_full_slate_before_player_fallback():
    names=[f'Player {i}' for i in range(1,13)]
    bulk_profiles={
        ctx._norm(name): {
            'player_name': name, 'team':'ATL', 'position':'G',
            'provider_ids': {'basketball_reference': f'p{i:02d}'},
            'headshot':'', 'current_games':[],
            'prior_games':[{'game_date':'2026-04-12','minutes':30,'points':10+i,'rebounds':5,'assists':4}],
            'stats_source':'Basketball-Reference daily leaders',
        }
        for i,name in enumerate(names, start=1)
    }
    fallback_calls=[]
    out=ctx.collect_nba_pra_player_context(
        date(2026,10,21), names, team_codes=['ATL'],
        official_loader=lambda *_: {'status':'DEGRADED','diagnostic_state':'NO_ELIGIBLE_HISTORY','profiles':{}},
        basketball_reference_index_loader=lambda *_: {'status':'HEALTHY','diagnostic_state':'INDEX_OK','profiles':{}},
        basketball_reference_bulk_history_loader=lambda *_args, **_kwargs: {
            'status':'HEALTHY','diagnostic_state':'RESOLVED_12_OF_12','profiles':bulk_profiles,
        },
        basketball_reference_loader=lambda _day, requested: fallback_calls.append(list(requested)) or {'profiles':{}},
        cbs_roster_loader=lambda _team: {},
    )
    assert out['verified_players'] == 12
    assert out['requested_players'] == 12
    assert fallback_calls == []
    assert out['history_budget'] >= 12


def test_context_router_sends_only_bulk_unresolved_players_to_individual_fallback():
    names=['Alpha One','Beta Two','Gamma Three']
    bulk={
        ctx._norm('Alpha One'):{'player_name':'Alpha One','team':'ATL','position':'G','provider_ids':{},'headshot':'','current_games':[], 'prior_games':[{'game_date':'2026-04-12','minutes':30,'points':10,'rebounds':5,'assists':4}],'stats_source':'Basketball-Reference daily leaders'},
        ctx._norm('Beta Two'):{'player_name':'Beta Two','team':'ATL','position':'G','provider_ids':{},'headshot':'','current_games':[], 'prior_games':[{'game_date':'2026-04-12','minutes':30,'points':11,'rebounds':5,'assists':4}],'stats_source':'Basketball-Reference daily leaders'},
    }
    calls=[]
    def fallback(_day, requested):
        calls.append(list(requested))
        return {'status':'HEALTHY','diagnostic_state':'ONE','profiles':{ctx._norm('Gamma Three'):{'player_name':'Gamma Three','team':'ATL','position':'G','provider_ids':{},'headshot':'','current_games':[], 'prior_games':[{'game_date':'2026-04-11','minutes':28,'points':9,'rebounds':4,'assists':3}],'stats_source':'Basketball-Reference'}}}
    out=ctx.collect_nba_pra_player_context(
        date(2026,10,21), names, team_codes=['ATL'],
        official_loader=lambda *_: {'status':'DEGRADED','diagnostic_state':'NO_ELIGIBLE_HISTORY','profiles':{}},
        basketball_reference_index_loader=lambda *_: {'status':'HEALTHY','diagnostic_state':'INDEX_OK','profiles':{}},
        basketball_reference_bulk_history_loader=lambda *_args, **_kwargs: {'status':'DEGRADED','diagnostic_state':'RESOLVED_2_OF_3','profiles':bulk},
        basketball_reference_loader=fallback,
        cbs_roster_loader=lambda _team: {},
    )
    assert calls == [['Gamma Three']]
    assert out['verified_players'] == 3


def test_default_bulk_dates_need_no_reference_schedule_page():
    current, prior = ctx._default_reference_bulk_dates(date(2026,10,21))
    assert current[0] == '2026-10-20'
    assert '2026-10-20' in current
    assert prior[0] == '2026-04-12'
    assert len(current) <= 32
    assert len(prior) <= 45


def test_team_codes_use_cbs_identity_before_spending_bref_identity_requests():
    calls={'index':0}
    def index_loader(*_args):
        calls['index'] += 1
        return {'status':'DEGRADED','profiles':{},'diagnostic_state':'SHOULD_NOT_RUN'}
    cbs={ctx._norm('Alpha One'):{'player_name':'Alpha One','team':'ATL','position':'G','provider_ids':{'cbs_sports':'1'},'headshot':'x','current_games':[],'prior_games':[],'stats_source':'CBS Sports roster verification'}}
    history={ctx._norm('Alpha One'):{'player_name':'Alpha One','team':'ATL','position':'G','provider_ids':{},'headshot':'','current_games':[],'prior_games':[{'game_date':'2026-04-12','minutes':30,'points':10,'rebounds':5,'assists':4}],'stats_source':'Basketball-Reference daily leaders'}}
    out=ctx.collect_nba_pra_player_context(
        date(2026,10,21), ['Alpha One'], team_codes=['ATL'],
        official_loader=lambda *_:{'status':'DEGRADED','profiles':{},'diagnostic_state':'NO_HISTORY'},
        basketball_reference_index_loader=index_loader,
        cbs_roster_loader=lambda _team:cbs,
        basketball_reference_bulk_history_loader=lambda *_a,**_k:{'status':'HEALTHY','profiles':history,'diagnostic_state':'ONE'},
    )
    assert calls['index'] == 0
    assert out['profiles'][ctx._norm('Alpha One')]['data_state'] == 'VERIFIED'


def test_history_merge_preserves_current_identity_team_over_prior_history_team():
    key=ctx._norm('Trade Player')
    profiles={key:ctx._normalize_profile('Trade Player',{
        'player_name':'Trade Player','team':'MIA','position':'SF',
        'provider_ids':{'cbs_sports':'99'},'headshot':'https://headshot/current.png',
        'current_games':[],'prior_games':[],'stats_source':'CBS Sports roster verification',
    })}
    history={key:{
        'player_name':'Trade Player','team':'GSW','position':'',
        'provider_ids':{'basketball_reference':'tradepl01'},'headshot':'',
        'current_games':[],'prior_games':[{'game_date':'2026-04-12','minutes':34,'points':20,'rebounds':5,'assists':4}],
        'stats_source':'Basketball-Reference daily leaders',
    }}
    ctx._merge_provider_rows(profiles,['Trade Player'],history)
    row=profiles[key]
    assert row['team'] == 'MIA'
    assert row['position'] == 'SF'
    assert row['headshot'] == 'https://headshot/current.png'
    assert row['provider_ids']['cbs_sports'] == '99'
    assert row['provider_ids']['basketball_reference'] == 'tradepl01'
    assert len(row['prior_games']) == 1


def _cbs_table(title, rows):
    headers=['date','opponent','result','fpts','min','pts','reb','ast','stl']
    head=''.join(f'<th class="TableBase-headTh">{h}</th>' for h in headers)
    body=''.join('<tr class="TableBase-bodyTr">'+''.join(f'<td class="TableBase-bodyTd">{v}</td>' for v in row)+'</tr>' for row in rows)
    return f'<div id="TableBase" class="TableBase"><h4 class="TableBase-title">{title}</h4><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def test_cbs_game_log_parser_uses_regular_season_only_and_maps_pra_minutes():
    html=(
      _cbs_table('2025-26 Post-Season Game Log', [['Apr 14, 2026','@CHA','L','30','42','27','7','3','0']])+
      _cbs_table('2025-26 Regular Season Game Log', [
        ['Apr 12, 2026','vs ATL','W','11','26','4','2','2','1'],
        ['Apr 10, 2026','@WAS','W','21','23','11','3','5','1'],
      ])
    )
    rows=ctx._parse_cbs_game_log_html(html)
    assert len(rows) == 2
    assert rows[0] == {'game_date':'2026-04-12','minutes':26.0,'points':4.0,'rebounds':2.0,'assists':2.0}
    assert rows[1]['game_date'] == '2026-04-10'
    assert rows[1]['points'] == 11.0
    assert rows[1]['assists'] == 5.0


def test_bref_bulk_history_stops_immediately_on_rate_limit():
    calls=[]
    def blocked(day):
        calls.append(day)
        raise ctx.ReferenceHistoryRateLimited('429')
    result=ctx._reference_bulk_history_profiles(
        date(2026,10,21), ['Alpha One'],
        current_game_dates=['2026-10-20','2026-10-19'], prior_game_dates=['2026-04-12'],
        daily_page_loader=blocked,
    )
    assert calls == ['2026-10-20']
    assert result['profiles'] == {}
    assert 'RATE_LIMITED' in result['diagnostic_state']


def test_context_uses_cbs_history_after_bref_rate_limit_without_individual_bref_fanout():
    name='Alpha One'; key=ctx._norm(name); individual=[]
    identity={key:{'player_name':name,'team':'ATL','position':'G','provider_ids':{'cbs_sports':'100'},'headshot':'x','current_games':[],'prior_games':[],'stats_source':'CBS Sports roster verification'}}
    cbs_history={key:{**identity[key], 'prior_games':[{'game_date':'2026-04-12','minutes':31,'points':15,'rebounds':5,'assists':6}], 'stats_source':'CBS Sports game log'}}
    out=ctx.collect_nba_pra_player_context(
        date(2026,10,21), [name], team_codes=['ATL'],
        official_loader=lambda *_:{'status':'DEGRADED','profiles':{},'diagnostic_state':'NO_HISTORY'},
        cbs_roster_loader=lambda _team:identity,
        basketball_reference_bulk_history_loader=lambda *_a,**_k:{'status':'DEGRADED','profiles':{},'diagnostic_state':'BULK_HISTORY_RATE_LIMITED'},
        basketball_reference_loader=lambda _day,names: individual.append(list(names)) or {'profiles':{}},
        cbs_history_loader=lambda *_a,**_k:{'status':'HEALTHY','profiles':cbs_history,'diagnostic_state':'RESOLVED_1_OF_1'},
    )
    assert individual == []
    assert out['verified_players'] == 1
    assert out['profiles'][key]['stats_source'] == 'CBS Sports game log'
    assert out['provider_health']['cbs_sports_history']['status'] == 'HEALTHY'


def test_cbs_history_uses_canonical_identity_name_for_game_log_url(monkeypatch):
    calls=[]
    regular=_cbs_table('2025-26 Regular Season Game Log', [['Apr 10, 2026','@WAS','W','21','23','11','3','5','1']])
    def fake_document(provider_id, player_name, season_start_year):
        calls.append((provider_id,player_name,season_start_year))
        return regular if season_start_year == 2025 else ''
    monkeypatch.setattr(ctx,'_cbs_game_log_document',fake_document)
    seed={
      'player_name':'Nickeil Alexander-Walker','team':'ATL','position':'SG',
      'provider_ids':{'cbs_sports':'2893425'},'headshot':'x','current_games':[],'prior_games':[],
      'stats_source':'CBS Sports roster verification',
    }
    row=ctx._cbs_player_history('N Alexander-Walker',date(2026,10,21),seed)
    assert calls == [
      ('2893425','Nickeil Alexander-Walker',2026),
      ('2893425','Nickeil Alexander-Walker',2025),
    ]
    assert row['player_name'] == 'Nickeil Alexander-Walker'
    assert row['team'] == 'ATL'
    assert len(row['prior_games']) == 1


def test_cbs_slug_removes_apostrophes_instead_of_splitting_names():
    assert ctx._cbs_player_slug("De'Anthony Melton") == 'deanthony-melton'
    assert ctx._cbs_player_slug("Day'Ron Sharpe") == 'dayron-sharpe'
    assert ctx._cbs_player_slug("Royce O'Neale") == 'royce-oneale'
    assert ctx._cbs_player_slug("Kel'el Ware") == 'kelel-ware'


def test_market_card_displays_prior_form_when_current_season_is_empty():
    from datetime import datetime, timezone
    from nba_pra_page1_ui_v2 import build_market_row_html
    item={
      'player_name':'Example Player','team':'ATL','position':'G','headshot':'','team_logo':'',
      'availability':'No verified injury flag',
      'featured_quote':{'sportsbook':'FanDuel','line':20.5,'over_price':-110,'under_price':-120,'observed_at_utc':'2026-10-21T16:42:00Z'},
      'quotes':[{'sportsbook':'FanDuel','line':20.5,'over_price':-110,'under_price':-120,'observed_at_utc':'2026-10-21T16:42:00Z'}],
      'model':{
        'projection':24.0,'sigma':6.0,
        'current':{'sample':0,'average':None,'median':None,'l5':None,'l10':None,'sigma':None,'minutes':None},
        'prior':{'sample':40,'average':23.0,'median':22.5,'l5':25.4,'l10':24.1,'sigma':6.0,'minutes':31.7},
        'basis':'PRIOR-SEASON BASELINE',
      },
      'grade':{'edge':3.5,'over_probability':0.72,'lean':'OVER','confidence':'HIGH'},
    }
    html=build_market_row_html(item,now_utc=datetime(2026,10,21,16,42,tzinfo=timezone.utc))
    assert '<b>L5</b> 25.4' in html
    assert '<b>L10</b> 24.1' in html
    assert '<b>MIN</b> 31.7' in html
    assert '72%' in html
    assert '>OVER<' in html
