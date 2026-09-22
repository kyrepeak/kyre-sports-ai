"""MLB Daily Game Picks V1.1 — Step 2 candidate-pool + market-health layer.

Builds on the verified Step 1 game shell. This version DOES NOT rank picks.
It only inventories which existing markets have eligible candidates for each game
and exposes a compact audit panel so Step 3 can normalize/rank clean inputs later.
"""
from __future__ import annotations

import html
import pandas as pd
import streamlit as st

import mlb_daily_game_picks_v10 as base
import mlb_matchup_hub_v10 as matchup

VERSION = "MLB Daily Game Picks V1.1 • STEP 2"
MARKETS = ("1+ Hit","Home Run","H+R+RBI","Pitcher Strikeouts","Moneyline","Run Line","Total")


def _esc(v):
    return html.escape(str(v or ""))


def _is_tbd(v):
    s=str(v or "").strip().lower()
    return s in {"","—","tbd","none","nan","probable starter tbd"}


def _candidate_pool(row):
    """Eligibility inventory only; no probabilities or ranking scores are computed."""
    try:
        hitters=matchup._hitters_for_game(row) or []
    except Exception:
        hitters=[]

    # Keep game identity attached so doubleheaders never share candidate state.
    game_pk=base._txt(row,"game_pk","gamePk",default="—")
    away=base._txt(row,"away_team","away_name")
    home=base._txt(row,"home_team","home_name")
    away_sp=base._txt(row,"away_pitcher","away_probable_pitcher","away_starter",default="TBD")
    home_sp=base._txt(row,"home_pitcher","home_probable_pitcher","home_starter",default="TBD")

    hitter_names=[f"{p.get('name')} ({p.get('team')})" for p in hitters if p.get('name')]
    starters=[x for x in (away_sp,home_sp) if not _is_tbd(x)]

    pools={
        "1+ Hit": {"ready":len(hitters)>0,"count":len(hitters),"items":hitter_names,"source":"confirmed lineup / active roster"},
        "Home Run": {"ready":len(hitters)>0,"count":len(hitters),"items":hitter_names,"source":"confirmed lineup / active roster"},
        "H+R+RBI": {"ready":len(hitters)>0,"count":len(hitters),"items":hitter_names,"source":"confirmed lineup / active roster"},
        "Pitcher Strikeouts": {"ready":len(starters)>0,"count":len(starters),"items":starters,"source":"probable starters"},
        "Moneyline": {"ready":not _is_tbd(away) and not _is_tbd(home),"count":2,"items":[away,home],"source":"verified game teams"},
        "Run Line": {"ready":not _is_tbd(away) and not _is_tbd(home),"count":2,"items":[away,home],"source":"verified game teams"},
        "Total": {"ready":not _is_tbd(away) and not _is_tbd(home),"count":2,"items":["Over","Under"],"source":"verified game market sides"},
    }
    return {"game_pk":game_pk,"pools":pools,"hitters":hitters,"starters":starters}


def _health_html(inv):
    cells=[]
    for market in MARKETS:
        d=inv["pools"][market]
        state="READY" if d["ready"] else "PENDING"
        cls="ready" if d["ready"] else "pending"
        cells.append(f'''<div class="dgp-health {cls}"><span>{_esc(market)}</span><b>{state}</b><small>{int(d['count'])} candidate{'s' if int(d['count'])!=1 else ''}</small></div>''')
    return '<div class="dgp-healthgrid">'+''.join(cells)+'</div>'


def _step2_css():
    st.markdown("""
<style>
.dgp-health-title{font-size:11px;letter-spacing:1.4px;font-weight:900;color:#9eb3c8;text-transform:uppercase;margin:12px 0 8px}
.dgp-healthgrid{display:grid;grid-template-columns:repeat(7,1fr);gap:7px;margin:0 0 12px}
.dgp-health{border:1px solid #29435e;border-radius:12px;background:#0c1b2d;padding:9px 8px;min-height:68px}.dgp-health span{display:block;color:#dbe7f4;font-size:10px;font-weight:850;line-height:1.15}.dgp-health b{display:block;font-size:10px;margin-top:7px}.dgp-health small{display:block;color:#748aa1;font-size:9px;margin-top:3px}.dgp-health.ready b{color:#36dc7c}.dgp-health.pending b{color:#e7b84d}
.dgp-pool-note{font-size:11px;color:#8398ae;margin:4px 0 10px}
@media(max-width:900px){.dgp-healthgrid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:620px){.dgp-healthgrid{grid-template-columns:repeat(2,1fr)}}
</style>
""",unsafe_allow_html=True)


def _render_game_step2(row,idx):
    away=base._txt(row,"away_team","away_name")
    home=base._txt(row,"home_team","home_name")
    away_id=base._txt(row,"away_team_id",default="")
    home_id=base._txt(row,"home_team_id",default="")
    time=base._txt(row,"first_pitch_et","game_time_et","start_time_et","game_time")
    venue=base._txt(row,"venue_name","venue")
    status=base._txt(row,"status","game_status",default="Scheduled")
    away_sp=base._txt(row,"away_pitcher","away_probable_pitcher","away_starter",default="TBD")
    home_sp=base._txt(row,"home_pitcher","home_probable_pitcher","home_starter",default="TBD")
    confirmed=base._confirmed_flag(row)
    lineup_text="✅ LINEUPS CONFIRMED" if confirmed else "🕒 LINEUPS PENDING"
    gamepk=base._txt(row,"game_pk","gamePk",default="—")
    inv=_candidate_pool(row)
    ready=sum(1 for m in MARKETS if inv["pools"][m]["ready"])

    st.markdown(f'''
<div class="dgp-game">
 <div class="dgp-top"><div class="dgp-num">GAME {idx} • MLB GAME ID {_esc(gamepk)}</div><div class="dgp-state">{_esc(lineup_text)}</div></div>
 <div class="dgp-match">
  <div class="dgp-team"><img src="{_esc(base._logo(away_id))}">{_esc(away)}</div>
  <div class="dgp-at">@</div>
  <div class="dgp-team"><img src="{_esc(base._logo(home_id))}">{_esc(home)}</div>
 </div>
 <div class="dgp-meta">{_esc(time)} ET • {_esc(venue)} • {_esc(status)}</div>
 <div class="dgp-starters">
  <div class="dgp-start"><span>Away probable starter</span><b>{_esc(away_sp)}</b></div>
  <div class="dgp-start"><span>Home probable starter</span><b>{_esc(home_sp)}</b></div>
 </div>
 <div class="dgp-health-title">Step 2 • Market availability</div>
 {_health_html(inv)}
 <div class="dgp-pool-note">{ready}/7 markets have an eligible candidate pool for MLB Game ID {_esc(gamepk)}. Availability is not a recommendation or ranking.</div>
 <div class="dgp-slots">
  <div class="dgp-slot"><div class="dgp-slotnum">🥇 PICK 1</div><div class="dgp-empty">Waiting for Step 3</div><div class="dgp-wait">Candidate pools are connected; ranking is intentionally disabled.</div></div>
  <div class="dgp-slot"><div class="dgp-slotnum">🥈 PICK 2</div><div class="dgp-empty">Waiting for Step 3</div><div class="dgp-wait">No cross-market score has been calculated yet.</div></div>
  <div class="dgp-slot"><div class="dgp-slotnum">🥉 PICK 3</div><div class="dgp-empty">Waiting for Step 3</div><div class="dgp-wait">No pick is forced before normalization is defined.</div></div>
 </div>
</div>''',unsafe_allow_html=True)

    with st.expander(f"🔎 Candidate pool audit • Game {idx} • MLB ID {gamepk}", expanded=False):
        for market in MARKETS:
            d=inv["pools"][market]
            status_txt="✅ READY" if d["ready"] else "🕒 PENDING"
            st.markdown(f"**{market} — {status_txt} — {d['count']} candidates**")
            st.caption(f"Eligibility source: {d['source']}")
            if d["items"]:
                preview=d["items"][:18]
                st.write(" • ".join(map(str,preview)) + (" • …" if len(d["items"])>18 else ""))
            else:
                st.write("No eligible candidates returned yet.")


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    base._css(); _step2_css()
    if games_df is None or games_df.empty:
        st.info("No verified MLB games are available for the selected date.")
        return
    frame=base._sort_games(games_df)
    day=base._txt(frame.iloc[0],"game_date",default="")[:10]
    if "game_pk" in frame.columns:
        try: verified=int((pd.to_numeric(frame["game_pk"],errors="coerce")>0).sum())
        except Exception: verified=len(frame)
    else: verified=len(frame)

    st.markdown('''<div class="dgp-hero"><div class="dgp-kicker">KYRE SPORTS AI • DAILY GAME PICKS • STEP 2</div><div class="dgp-title">🏆 Top 3 Picks — Every MLB Game</div><div class="dgp-sub">Step 2 connects eligible candidate pools from 1+ Hit, Home Run, H+R+RBI, Pitcher Strikeouts, Moneyline, Run Line and Total. This page still does not rank or recommend anything; Step 3 will define cross-market normalization first.</div></div>''',unsafe_allow_html=True)
    st.success(f"✅ Step 2 candidate layer ready • {day or 'selected date'} • {verified}/{len(frame)} verified games • 7 eligible market families checked per game • 0 picks ranked")
    for i,(_,row) in enumerate(frame.iterrows(),1):
        _render_game_step2(row,i)
    st.markdown(f'<div class="dgp-foot">{VERSION} • candidate eligibility only • no probabilities compared across markets • no ranking active • doubleheaders isolated by MLB game ID • existing production engines unchanged</div>',unsafe_allow_html=True)
