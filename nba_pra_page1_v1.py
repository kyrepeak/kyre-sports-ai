"""NBA PRA Page 1/3 — Premium Command Center."""
from __future__ import annotations
from html import escape
import streamlit as st
from nba_pra_page1_data_v1 import load_page1_snapshot
from nba_pra_page1_model_v1 import SPORTSBOOK_PROJECTION_INFLUENCE
from nba_pra_page1_ui_v1 import FILTER_OPTIONS, TEAM_LOGO_BASE, SESSION_PLAYER, _css, _item, _card
MODEL_VERSION="NBA PRA PAGE 1/3 • COMMAND CENTER V1"

def render_nba_pra_page1():
    _css(); st.markdown('<div class="np1-hero"><div class="np1-k">KYRE SPORTS AI • NBA PRA INTELLIGENCE</div><div class="np1-t">🏀 NBA PRA Command Center</div><div class="np1-s">Page 1/3 • Find the opportunity • automatic active slate • multi-book intelligence</div></div>',unsafe_allow_html=True)
    with st.spinner("Loading verified NBA PRA intelligence…"): snap=load_page1_snapshot()
    games=snap.get("games") or []; market=snap.get("market") or {}; profiles=snap.get("profiles") or {}; injuries=snap.get("injury_players") or {}; sources=snap.get("sources") or {}
    st.markdown(f'<span class="np1-chip">SLATE {escape(str(snap.get("slate_date") or "—"))}</span><span class="np1-chip">{len(games)} GAMES</span><span class="np1-chip">SPORTSGAMEODDS {(sources.get("sgo") or {}).get("verification","UNAVAILABLE")}</span><span class="np1-chip">ODDS-API.IO {(sources.get("odds_api") or {}).get("verification","UNAVAILABLE")}</span>',unsafe_allow_html=True)
    if games:
        game_html=[]
        for g in games:
            away=str(g.get("away_tricode") or "—"); home=str(g.get("home_tricode") or "—"); tip=str(g.get("tip_phoenix") or g.get("status") or "Scheduled")
            al=TEAM_LOGO_BASE.format(code=away.lower()); hl=TEAM_LOGO_BASE.format(code=home.lower())
            game_html.append(f'<div class="np1-game"><div><img src="{escape(al)}"> <b>{escape(away)}</b> @ <b>{escape(home)}</b> <img src="{escape(hl)}"></div><small>{escape(tip)}</small></div>')
        st.markdown('<div class="np1-games">'+''.join(game_html)+'</div>',unsafe_allow_html=True)
    if not market:
        st.markdown('<div class="np1-warn"><b>PRA MARKET UNAVAILABLE</b><br>No verified PRA line is available from the configured providers. No market line or probability is fabricated.</div>',unsafe_allow_html=True); return
    items=[_item(k,q,profiles.get(k,{"player_name":q.get("player_name")}),injuries.get(k)) for k,q in market.items()]
    ranked=sorted(items,key=lambda x:max(x["grade"].get("over_probability") or .5,1-(x["grade"].get("over_probability") or .5)),reverse=True)
    selected_filter=st.radio("PRA filters",FILTER_OPTIONS,horizontal=True,label_visibility="collapsed",key="np1-filter")
    if selected_filter=="TOP EDGES": ranked=[x for x in ranked if x["grade"].get("edge") is not None][:10]
    elif selected_filter=="OVER": ranked=[x for x in ranked if x["grade"].get("lean")=="OVER"]
    elif selected_filter=="UNDER": ranked=[x for x in ranked if x["grade"].get("lean")=="UNDER"]
    elif selected_filter=="HIGH CONFIDENCE": ranked=[x for x in ranked if x["grade"].get("confidence")=="HIGH"]
    st.markdown('<div class="np1-sec">FEATURED INTELLIGENCE</div>',unsafe_allow_html=True); top=ranked[:3]; cols=st.columns(len(top)) if top else []
    for idx,item in enumerate(top):
        with cols[idx]: _card(item,idx+1)
    st.markdown('<div class="np1-sec">ALL PRA PLAYERS</div>',unsafe_allow_html=True)
    for start in range(0,len(ranked),2):
        cols=st.columns(2)
        for offset,item in enumerate(ranked[start:start+2]):
            with cols[offset]: _card(item)
