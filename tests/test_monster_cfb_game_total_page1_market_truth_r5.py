from __future__ import annotations

from contextlib import contextmanager

import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as router


def obs(book, market, *, value, side=None, home=None, away=None, ts='2026-10-17T04:20:00+00:00', transport='action_network'):
    row={
        'game_id':'401856720','sportsbook':book,'provider_id':book.casefold().replace(' ','_'),
        'market_type':market,'phase':'pregame','value':value,'observed_at_utc':ts,
        'identity_verified':True,'transport':transport,'provenance':'test verified book quote','fabrication':False,
    }
    if side: row['side']=side
    if home is not None: row['home_value']=home
    if away is not None: row['away_value']=away
    return row


def game():
    return {
      'event_id':'401856720',
      'away':{'id':'344','name':'Mississippi State Bulldogs','record':'4-1','conference':'SEC'},
      'home':{'id':'99','name':'LSU Tigers','record':'4-2','conference':'SEC'},
      'venue':'Tiger Stadium (LA)','city':'Baton Rouge, LA','broadcast':'ESPN, Disney+',
      'market_observations':[
        obs('DraftKings','moneyline',value=-800,home=-800,away=550,ts='2026-10-17T04:18:00+00:00'),
        obs('DraftKings','spread',value=-17.5,home=-17.5,away=17.5,ts='2026-10-17T04:18:00+00:00'),
        obs('DraftKings','game_total',value=55.5,ts='2026-10-17T04:18:00+00:00'),
        obs('FanDuel','moneyline',value=-880,home=-880,away=580),
        obs('FanDuel','spread',value=-16.5,home=-16.5,away=16.5),
        obs('FanDuel','game_total',value=56.5),
        obs('ESPN BET','spread',value=-17,home=-17,away=17,ts='2026-10-17T04:15:00+00:00',transport='espn_scoreboard'),
        obs('ESPN BET','game_total',value=56.5,ts='2026-10-17T04:15:00+00:00',transport='espn_scoreboard'),
      ],
      'status':{'state':'Scheduled','detail':'9:00 AM MST'},
      'subdivisions':['FBS'],
    }


def test_installed_page1_uses_one_labeled_complete_book_quote():
    with router.install_daily_slate_page1():
        page=router.daily_fallback.page
        card=page.card_view_model(game())
        assert card.get('market_book') == 'FanDuel'
        assert card.get('away_moneyline') == '+580'
        assert card.get('home_moneyline') == '-880'
        assert card.get('away_spread') == '+16.5'
        assert card.get('home_spread') == '-16.5'
        assert card.get('total') == 'O/U 56.5'
        assert card.get('market_source_count',0) >= 3


def test_installed_page1_exposes_multisource_enricher_and_compact_more():
    with router.install_daily_slate_page1():
        page=router.daily_fallback.page
        assert callable(getattr(page,'enrich_games_with_market_truth',None))
        helper=getattr(page,'market_more_html',None)
        assert callable(helper)
        html=helper(game(), page.card_view_model(game()))
        assert 'FanDuel' in html
        assert 'Event ID' in html and 'Team IDs' in html and 'Tiger Stadium' in html
        assert html.count('<div') >= 3
