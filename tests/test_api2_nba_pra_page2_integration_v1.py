from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import inspect


def _schedule():
    return {
        'verification':'VERIFIED',
        'games':[
            {'gameStatus':1,'status':'UPCOMING','game_date_phoenix':'2026-10-21','tip_utc':'2026-10-22T02:00:00Z','away_tricode':'MIN','away_name':'Minnesota Timberwolves','home_tricode':'LAL','home_name':'Los Angeles Lakers'},
            {'gameStatus':1,'status':'UPCOMING','game_date_phoenix':'2026-10-21','tip_utc':'2026-10-22T02:30:00Z','away_tricode':'MIA','away_name':'Miami Heat','home_tricode':'ORL','home_name':'Orlando Magic'},
        ],
    }


def _market():
    obs=[]
    for name,away,home,line in [
        ('Anthony Edwards','Minnesota Timberwolves','Los Angeles Lakers',36.5),
        ('Andrew Wiggins','Miami Heat','Orlando Magic',29.5),
    ]:
        for side in ('over','under'):
            obs.append({'provider':'FanDuel','player_name':name,'sportsbook':'FanDuel','side':side,'line':line,'price':-110,'observed_at_utc':'2026-10-21T17:30:00Z','away_team':away,'home_team':home})
    return {'verification':'VERIFIED','observations':obs}


def test_page2_selected_loader_requests_context_for_one_player_only():
    from nba_pra_page2_api_only_v1 import load_page2_snapshot_v1
    calls=[]
    def context(day,names,team_codes=None):
        calls.append((list(names),list(team_codes or [])))
        return {'verification':'VERIFIED','profiles':{'anthonyedwards':{
            'player_name':'Anthony Edwards','team':'MIN','position':'SG','headshot':'ant.png',
            'current_games':[],'prior_games':[{'game_date':'2026-04-10','minutes':35,'points':25,'rebounds':6,'assists':5}],
        }}}
    snap=load_page2_snapshot_v1(
        'anthonyedwards',
        now=datetime(2026,10,21,17,0,tzinfo=timezone.utc),
        schedule_loader=lambda **_: _schedule(),
        api_loader=lambda *_: _market(),
        player_context_loader=context,
        injury_loader=lambda games,**_: {'verification':'VERIFIED','players':{}},
    )
    assert calls and calls[0][0] == ['Anthony Edwards']
    assert len(calls[0][0]) == 1
    assert set(snap['market']) == {'anthonyedwards'}
    assert set(snap['profiles']) == {'anthonyedwards'}
    assert len(snap['games']) == 1
    assert snap['games'][0]['away_tricode']=='MIN' and snap['games'][0]['home_tricode']=='LAL'


def test_page2_loader_keeps_multibook_quotes_separate():
    from nba_pra_page2_api_only_v1 import load_page2_snapshot_v1
    market=_market()
    for side in ('over','under'):
        market['observations'].append({'provider':'DraftKings','player_name':'Anthony Edwards','sportsbook':'DraftKings','side':side,'line':37.5,'price':-105,'observed_at_utc':'2026-10-21T17:31:00Z','away_team':'Minnesota Timberwolves','home_team':'Los Angeles Lakers'})
    context=lambda day,names,team_codes=None:{'profiles':{'anthonyedwards':{'player_name':'Anthony Edwards','team':'MIN','current_games':[],'prior_games':[]}}}
    snap=load_page2_snapshot_v1('anthonyedwards',now=datetime(2026,10,21,17,0,tzinfo=timezone.utc),schedule_loader=lambda **_:_schedule(),api_loader=lambda *_:market,player_context_loader=context,injury_loader=lambda *a,**k:{'players':{}})
    quotes=snap['market']['anthonyedwards']['quotes']
    assert [(q['sportsbook'],q['line']) for q in quotes] == [('FanDuel',36.5),('DraftKings',37.5)]


def test_runtime_overlay_delegates_nba_pra_to_page2_selector():
    text=Path('streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py').read_text()
    assert 'nba_pra_runtime_v2' in text
    assert 'render_nba_pra_runtime_v2' in text
    assert 'return page.render_nba_pra_page1_v2()' not in text


def test_active_page2_path_has_no_forbidden_provider_or_direct_app_scrape():
    active=[
        'nba_pra_runtime_v2.py','nba_pra_page2_v1.py','nba_pra_page2_context_v1.py','nba_pra_page2_line_lab_v1.py',
        'nba_pra_page2_matchup_v1.py','nba_pra_page2_matchup_api_v1.py','nba_pra_page2_api_only_v1.py',
        'streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py',
    ]
    joined='\n'.join(Path(path).read_text().casefold() for path in active if Path(path).exists())
    for banned in ('sportsgameodds','sports_game_odds','espn bet','espnbet'):
        assert banned not in joined
    # App-facing Page-2 files may mention only the Kyre gateway URL/client; CBS belongs server-side under runless_v2.
    app='\n'.join(Path(path).read_text().casefold() for path in active if Path(path).exists() and not path.startswith('runless_v2/'))
    assert 'cbssports.com' not in app


def test_no_variance_line_lab_remains_fail_closed():
    from nba_pra_page2_line_lab_v1 import evaluate_line
    result=evaluate_line(31.2,None,36.5)
    assert result['edge']==-5.3
    assert result['over_probability'] is None and result['under_probability'] is None
    assert result['score'] is None and result['lean']=='PASS'
