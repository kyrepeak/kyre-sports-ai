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


def _direct_action_payload():
    return {"games":[{"id":289492,"start_time":"2026-10-17T16:00:00.000Z","away_team_id":1,"home_team_id":2,"teams":[{"id":1,"full_name":"Mississippi State Bulldogs","display_name":"Mississippi State","location":"Mississippi State","abbr":"MSST"},{"id":2,"full_name":"LSU Tigers","display_name":"LSU","location":"LSU","abbr":"LSU"}],"markets":{"69":{"event":{"moneyline":[{"side":"away","odds":580,"line_status":"normal","is_live":False},{"side":"home","odds":-880,"line_status":"normal","is_live":False}],"spread":[{"side":"away","value":16.5,"line_status":"normal","is_live":False},{"side":"home","value":-16.5,"line_status":"normal","is_live":False}],"total":[{"side":"over","value":56.5,"line_status":"normal","is_live":False}]}}}}]}


def test_direct_action_json_parser_preserves_fanduel_quote():
    rows=router._parse_action_api(_direct_action_payload(), "2026-10-17T05:00:00+00:00")
    quote,quotes=router.page1_market_truth.select_featured_book_quote(rows[0]["observations"])
    assert (quote["book"],quote["away_moneyline"],quote["home_moneyline"],quote["away_spread"],quote["home_spread"],quote["total"]) == ("FanDuel",580,-880,16.5,-16.5,56.5)
    assert "FanDuel" in quotes


def test_route_owns_direct_json_api_primary_contract():
    assert router.ACTION_API_URL.startswith("https://api.actionnetwork.com/web/v2/scoreboard/ncaaf")
    assert callable(router._fetch_action_json_board) and callable(router._install_action_json_primary)
