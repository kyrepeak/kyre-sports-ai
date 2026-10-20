"""NBA PRA Page 1/3 — Premium Command Center."""
from __future__ import annotations
from html import escape
from typing import Any, Mapping
import streamlit as st
from nba_pra_page1_data_v1 import load_page1_snapshot
from nba_pra_page1_model_v1 import SPORTSBOOK_PROJECTION_INFLUENCE, grade_market, project_pra
MODEL_VERSION="NBA PRA PAGE 1/3 • COMMAND CENTER V1"
FILTER_OPTIONS=("ALL PLAYERS","TOP EDGES","OVER","UNDER","HIGH CONFIDENCE")
TEAM_LOGO_BASE="https://a.espncdn.com/i/teamlogos/nba/500/{code}.png"
SESSION_LINE_HISTORY="ks_nba_pra_page1_line_history"; SESSION_PLAYER="ks_nba_pra_selected_player"

def _fmt(v:Any,d:int=1,missing:str="—")->str:
    try:return f"{float(v):.{d}f}"
    except (TypeError,ValueError):return missing
def _price(v:Any)->str:
    try:
        n=int(v); return f"+{n}" if n>0 else str(n)
    except (TypeError,ValueError):return "—"
def _remember(key:str,line:float|None):
    hist=st.session_state.setdefault(SESSION_LINE_HISTORY,{})
    if line is None:return None,None
    values=hist.setdefault(key,[float(line)])
    if values[-1]!=float(line): values.append(float(line))
    hist[key]=values[-12:]; return hist[key][0],hist[key][-1]
def _css():
    st.markdown('''<style>.np1-hero{padding:20px;border:1px solid #214a63;border-radius:22px;background:linear-gradient(145deg,#07131f,#02060a);margin-bottom:12px}.np1-k{color:#79ddff;font-weight:900;letter-spacing:.13em;font-size:.78rem}.np1-t{font-size:2rem;font-weight:950;color:#fff}.np1-s{color:#a9bccb}.np1-chip{display:inline-block;padding:5px 9px;border:1px solid #244862;border-radius:999px;background:#071522;color:#d5f4ff;font-size:.78rem;margin:3px}.np1-sec{color:#78dfff;font-size:.82rem;letter-spacing:.12em;font-weight:900;margin:18px 0 8px}.np1-card{padding:15px;border:1px solid #183a50;border-radius:18px;background:linear-gradient(155deg,#07131f,#03080e);margin-bottom:10px}.np1-name{font-size:1.12rem;font-weight:900;color:#fff}.np1-meta{font-size:.8rem;color:#91a8b9}.np1-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:10px}.np1-m{padding:8px;border-radius:10px;background:#071827;border:1px solid #12344a}.np1-m small{display:block;color:#7791a5;font-size:.66rem}.np1-m b{color:#f0fbff}.np1-big{font-size:1.38rem!important}.np1-note{margin-top:9px;color:#b7cbd9;font-size:.8rem}.np1-warn{padding:13px;border-radius:14px;background:#1b1407;border:1px solid #594620;color:#ffd993} .np1-games{display:flex;gap:9px;overflow-x:auto;padding:4px 0 10px;scrollbar-width:thin}.np1-game{min-width:185px;padding:10px;border:1px solid #163c54;border-radius:14px;background:#06111b;color:#eefaff}.np1-game img{width:28px;height:28px;object-fit:contain;vertical-align:middle}.np1-game small{color:#8ba2b5}@media(max-width:720px){.np1-t{font-size:1.55rem}.np1-grid{grid-template-columns:repeat(2,1fr)}}</style>''',unsafe_allow_html=True)
def _item(key,q,p,injury):
    model=project_pra(p.get("current_games") or [],p.get("prior_games") or []); grade=grade_market(model.get("projection"),q.get("line"),model.get("sigma")); return {"key":key,"quote":q,"profile":p,"injury":injury or {},"model":model,"grade":grade}
def _card(item:Mapping[str,Any],rank:int|None=None):
    q,p,i,m,g=item["quote"],item["profile"],item["injury"],item["model"],item["grade"]; op,now=_remember(item["key"],q.get("line")); prob=g.get("over_probability"); current=m.get("current") or {}; prior=m.get("prior") or {}; name=p.get("player_name") or q.get("player_name") or "Player"; head=p.get("headshot"); img=f'<img src="{escape(str(head))}" style="width:48px;height:48px;border-radius:50%;object-fit:cover">' if head else ''; availability=str(i.get("status") or "No verified injury flag"); movement="PRA MARKET UNAVAILABLE" if q.get("line") is None else (f"SESSION {op:.1f} → {now:.1f}" if op is not None else "SESSION START")
    st.markdown(f'''<div class="np1-card"><div style="display:flex;gap:10px;align-items:center">{img}<div><div class="np1-name">{('#'+str(rank)+' • ') if rank else ''}{escape(str(name))}</div><div class="np1-meta">{escape(str(p.get('team') or 'NBA'))} • {escape(str(p.get('position') or ''))} • {escape(' + '.join(q.get('providers') or []))}</div></div></div><div class="np1-grid"><div class="np1-m"><small>PRA LINE</small><b class="np1-big">{_fmt(q.get('line'))}</b></div><div class="np1-m"><small>KYRE AI</small><b class="np1-big">{_fmt(m.get('projection'),1,'BUILDING')}</b></div><div class="np1-m"><small>OVER PROBABILITY</small><b class="np1-big">{f'{prob*100:.0f}%' if prob is not None else 'BUILDING'}</b></div><div class="np1-m"><small>EDGE / LEAN</small><b>{_fmt(g.get('edge'))} • {escape(str(g.get('lean')))}</b></div><div class="np1-m"><small>CONFIDENCE</small><b>{escape(str(g.get('confidence')))}</b></div><div class="np1-m"><small>AVAILABILITY</small><b>{escape(availability)}</b></div><div class="np1-m"><small>CURRENT SEASON</small><b>{current.get('sample',0)} games • L5 {_fmt(current.get('l5'))}</b></div><div class="np1-m"><small>PRIOR-SEASON BASELINE</small><b>{prior.get('sample',0)} games • L10 {_fmt(prior.get('l10'))}</b></div><div class="np1-m"><small>MARKET</small><b>{q.get('book_count',0)} books • O {_price(q.get('over_price'))} / U {_price(q.get('under_price'))}</b></div></div><div class="np1-note"><b>{movement}</b> • {escape(str(m.get('basis') or 'HISTORY_UNAVAILABLE'))} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}%</div></div>''',unsafe_allow_html=True)
    if st.button(f"View {name} on Page 2",key=f"np1-{item['key']}",use_container_width=True): st.session_state[SESSION_PLAYER]=item["key"]
