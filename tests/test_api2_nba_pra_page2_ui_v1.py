from __future__ import annotations
from pathlib import Path


def _context():
    return {
        'state':'line_moved','line_moved':True,'line_moved_label':'LINE MOVED SINCE SELECTION',
        'player_name':'Anthony Edwards','team':'MIN','opponent':'LAL','availability':'AVAILABLE',
        'team_logo':'https://cdn.nba.com/min.svg','opponent_logo':'https://cdn.nba.com/lal.svg',
        'player':{
            'player_name':'Anthony Edwards','team':'MIN','position':'SG','headshot':'https://example.com/ant.png',
            'current_games':[],
            'prior_games':[
                {'game_date':'2026-04-10','minutes':35,'points':25,'rebounds':6,'assists':5},
                {'game_date':'2026-04-08','minutes':34,'points':20,'rebounds':7,'assists':4},
            ],
        },
        'game':{'game_id':'g1','tip_utc':'2026-10-22T02:00:00Z'},
        'selected_quote':{'sportsbook':'FanDuel','line':36.5,'over_price':-110,'under_price':-110,'observed_at_utc':'2026-10-21T17:30:00Z'},
        'current_quote':{'sportsbook':'FanDuel','line':37.5,'over_price':-105,'under_price':-115,'observed_at_utc':'2026-10-21T17:34:00Z'},
        'quotes':[
            {'sportsbook':'FanDuel','line':37.5,'over_price':-105,'under_price':-115,'observed_at_utc':'2026-10-21T17:34:00Z'},
            {'sportsbook':'DraftKings','line':36.5,'over_price':-110,'under_price':-110,'observed_at_utc':'2026-10-21T17:33:00Z'},
        ],
    }


def test_page2_html_contains_hybrid_s_tier_contract():
    from nba_pra_page2_v1 import build_page2_html
    model={'projection':31.2,'sigma':5.0,'current':{'sample':0},'prior':{'sample':10,'l5':30.4,'l10':31.1,'minutes':34.5}}
    line_result={'line':36.5,'edge':-5.3,'over_probability':0.14,'under_probability':0.86,'lean':'UNDER','confidence':'HIGH','score':9.4,'tier':'ELITE'}
    matchup={
        'points':{'rank':9,'value':111.8,'grade':'TOUGH'},'rebounds':{'rank':17,'value':44.4,'grade':'MEDIUM'},
        'assists':{'rank':17,'value':27.4,'grade':'MEDIUM'},'pra_rank':14,'matchup_grade':'MEDIUM',
        'rank_semantics':'NBA opponent rank: 1 = toughest/stingiest, 30 = most permissive',
        'evidence_period':'2026-27 PRESEASON BASELINE','source':'Kyre Sports API — CBS Sports opponent team stats',
    }
    html=build_page2_html(_context(),model,line_result,matchup,active_line=36.5)
    for text in ['Anthony Edwards','KYRE AI VERDICT','LINE LAB','RECENT FORM','OPPONENT RANK','MEDIUM','ROLE & MINUTES','INJURY / LINEUP IMPACT','PROJECTION BREAKDOWN','RISK FACTORS','FULL GAME LOG']:
        assert text in html
    assert 'ant.png' in html and 'min.svg' in html and 'lal.svg' in html
    assert 'LINE MOVED SINCE SELECTION' in html
    assert 'FanDuel' in html and 'DraftKings' in html
    assert 'L5' in html and 'L10' in html and 'MIN' in html
    assert 'Points' in html and '#9' in html
    assert 'Rebounds' in html and '#17' in html
    assert 'Assists' in html and '#17' in html
    assert 'No verified prior matchup sample.' in html
    assert '2026-27 PRESEASON BASELINE' in html


def test_page2_source_has_back_top_touch_slider_and_no_keyboard_primary_input():
    text=Path('nba_pra_page2_v1.py').read_text()
    assert '← Back to PRA Board' in text
    assert '↑ TOP' in text
    assert 'position:fixed' in text.replace(' ','')
    assert 'select_slider' in text
    assert 'text_input' not in text
    assert 'number_input' not in text


def test_game_log_marks_over_under_against_active_line():
    from nba_pra_page2_v1 import game_log_rows
    rows=game_log_rows(_context()['player'],36.5)
    assert rows[0]['pra']==36.0 and rows[0]['result']=='UNDER'
    assert rows[1]['pra']==31.0 and rows[1]['result']=='UNDER'

def test_line_lab_default_prefers_exact_tapped_quote_over_moved_live_quote():
    from nba_pra_page2_v1 import default_line_for_context
    ctx=_context()
    assert ctx['selected_quote']['line']==36.5 and ctx['current_quote']['line']==37.5
    assert default_line_for_context(ctx)==36.5
