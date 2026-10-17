from __future__ import annotations
from datetime import date
from pathlib import Path
import cfb_game_total_page1_polish_r4 as page
import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as router
ROOT=Path(__file__).resolve().parents[1]

def _quote(value): return {'selected_quote': {'value': value}, 'confidence': 'VERIFIED'}

def test_card_model_exposes_identity_location_and_team_moneylines(monkeypatch):
    monkeypatch.setattr(page,'build_game_market_context',lambda game_id,observations:{'current':{'game_total':_quote(56.5),'spread':_quote(-3.5),'moneyline_home':_quote(-165),'moneyline_away':_quote(145)},'opening':{'game_total':_quote(54.5)}})
    game={'event_id':'401856720','venue':'Tiger Stadium (LA)','city':'Baton Rouge, LA','broadcast':'ESPN','weather':{'temperature_f':81,'summary':'Clear','wind_mph':5},'away':{'id':'344','name':'Mississippi State Bulldogs','logo':'away.png','conference':'SEC'},'home':{'id':'99','name':'LSU Tigers','logo':'home.png','conference':'SEC'},'market_observations':[]}
    m=page.card_view_model(game)
    assert (m['event_id'],m['away_id'],m['home_id'])==('401856720','344','99')
    assert (m['away_logo'],m['home_logo'])==('away.png','home.png')
    assert (m['away_conference'],m['home_conference'])==('SEC','SEC')
    assert (m['away_moneyline'],m['home_moneyline'])==('+145','-165')
    assert (m['venue'],m['city'])==('Tiger Stadium (LA)','Baton Rouge, LA')
    assert (m['total'],m['opening_total'],m['total_move'])==('O/U 56.5','54.5','+2.0')

def test_date_strip_is_compact_routable_and_centered():
    selected=date(2026,10,17); days=page.date_nav_days(selected)
    assert len(days)==7 and days[3]==selected and days[0]==date(2026,10,14) and days[-1]==date(2026,10,20)
    href=page.date_nav_href(selected)
    assert 'ks_cfb_game_total_date=2026-10-17' in href and 'ks_sport=College+Football' in href and 'ks_cfb_market=Game+Total' in href

def test_successor_route_and_visual_contract():
    source=(ROOT/'cfb_game_total_page1_polish_r4.py').read_text(); css=(ROOT/'cfb_game_total_page1_polish_r4.css').read_text()
    assert router.PAGE1_DAILY_SLATE_ROUTE=='cfb_game_total_page1_daily_slate_v1'
    assert 'CFB GAME TOTALS' in source and 'Saturday Slate' in source and 'Jump to date' in source
    assert 'page1_polish.install_into' in (ROOT/'streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py').read_text()
    assert 'cfbgt-hero' in css and 'cfbgt-date-strip' in css and '.ks-route{display:none!important}' in css
    assert '← Previous' not in source and 'Next →' not in source

def test_polish_keeps_page2_and_model_boundaries_unchanged():
    assert page.MAY_MODIFY_MODEL is False and page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROBABILITY is False and page.MAY_MODIFY_RANKING is False
    assert page.MAY_MODIFY_SELECTION is False and page.MAY_MODIFY_OTHER_SPORTS is False
    assert page.MAY_MODIFY_SELECTED_GAME_RUNTIME is False and page.SPORTSBOOK_PROJECTION_INFLUENCE==0.0
    assert page.EVENT_QUERY_KEY and page.SELECTOR_SYNC_QUERY_KEY and page.view_game_href
