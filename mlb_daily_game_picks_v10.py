"""MLB Daily Game Picks V1.0 — Step 1 page shell.

Verified-slate game cards with matchup metadata and three intentionally empty pick
slots. No ranking, projection, correlation, or market-selection logic is active yet.
"""
from __future__ import annotations

import html
import math
import pandas as pd
import streamlit as st

VERSION = "MLB Daily Game Picks V1.0 • STEP 1"


def _esc(v):
    return html.escape(str(v or ""))


def _logo(team_id):
    try:
        return f"https://www.mlbstatic.com/team-logos/{int(float(team_id))}.svg"
    except Exception:
        return ""


def _txt(row, *keys, default="—"):
    for k in keys:
        try:
            v=row.get(k)
        except Exception:
            v=None
        if v is not None and str(v).strip() not in {"", "nan", "None"}:
            return str(v)
    return default


def _confirmed_flag(row):
    explicit=[]
    for k in ("lineup_confirmed","confirmed_lineups","lineups_confirmed","away_lineup_confirmed","home_lineup_confirmed"):
        try:
            v=row.get(k)
        except Exception:
            continue
        if v is not None and str(v).lower() not in {"nan","none",""}:
            explicit.append(bool(v))
    if explicit:
        return all(explicit)
    status=_txt(row,"status","game_status",default="").lower()
    if any(x in status for x in ("in progress","live","final","game over")):
        return True
    return False


def _sort_games(frame):
    if frame is None or frame.empty:
        return frame
    out=frame.copy()
    if "game_datetime" in out.columns:
        try:
            out["__sort"]=pd.to_datetime(out["game_datetime"],errors="coerce",utc=True)
            return out.sort_values("__sort",kind="stable").drop(columns=["__sort"]).reset_index(drop=True)
        except Exception:
            pass
    return out.reset_index(drop=True)


def _css():
    st.markdown("""
<style>
.dgp-hero{border:1px solid #284660;border-radius:24px;padding:22px 24px;background:linear-gradient(135deg,#0d1b31,#081321);margin:8px 0 18px}
.dgp-kicker{font-size:11px;letter-spacing:2px;font-weight:900;color:#54dbff;text-transform:uppercase}.dgp-title{font-size:34px;line-height:1.05;font-weight:950;color:#f7f9ff;margin:8px 0}.dgp-sub{font-size:14px;color:#9cafc4;line-height:1.5}
.dgp-game{border:1px solid #2a4864;border-radius:24px;padding:18px 18px 16px;background:#0a1728;margin:0 0 16px}.dgp-top{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}.dgp-num{font-size:11px;font-weight:900;letter-spacing:1.4px;color:#55d9ff}.dgp-state{font-size:10px;font-weight:900;border:1px solid #35516e;border-radius:999px;padding:5px 8px;color:#b7c8da}
.dgp-match{display:grid;grid-template-columns:1fr 48px 1fr;gap:10px;align-items:center}.dgp-team{text-align:center;color:#fff;font-weight:900;font-size:19px}.dgp-team img{height:52px;max-width:70px;display:block;margin:0 auto 7px}.dgp-at{text-align:center;color:#6785a2;font-size:20px;font-weight:950}.dgp-meta{text-align:center;color:#8fa4ba;font-size:12px;line-height:1.55;margin:12px 0 14px}
.dgp-starters{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:0 0 12px}.dgp-start{border:1px solid #263f59;border-radius:14px;background:#0e1d30;padding:10px 12px}.dgp-start span{display:block;color:#7891ab;font-size:9px;font-weight:900;letter-spacing:1px;text-transform:uppercase}.dgp-start b{display:block;color:#eef5ff;font-size:14px;margin-top:3px}
.dgp-slots{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.dgp-slot{min-height:90px;border:1px dashed #38536f;border-radius:16px;background:rgba(14,29,48,.55);padding:12px}.dgp-slotnum{font-size:10px;color:#54dbff;font-weight:900;letter-spacing:1px}.dgp-empty{font-size:14px;color:#b1c0cf;font-weight:800;margin-top:8px}.dgp-wait{font-size:10px;color:#70879f;margin-top:3px;line-height:1.35}
.dgp-foot{font-size:12px;color:#8195aa;margin:4px 0 18px}
@media(max-width:700px){.dgp-title{font-size:28px}.dgp-team{font-size:16px}.dgp-team img{height:44px}.dgp-slots{grid-template-columns:1fr}.dgp-starters{grid-template-columns:1fr 1fr}}
</style>
""",unsafe_allow_html=True)


def _render_game(row, idx):
    away=_txt(row,"away_team","away_name")
    home=_txt(row,"home_team","home_name")
    away_id=_txt(row,"away_team_id",default="")
    home_id=_txt(row,"home_team_id",default="")
    time=_txt(row,"first_pitch_et","game_time_et","start_time_et","game_time")
    venue=_txt(row,"venue_name","venue")
    status=_txt(row,"status","game_status",default="Scheduled")
    away_sp=_txt(row,"away_pitcher","away_probable_pitcher","away_starter",default="TBD")
    home_sp=_txt(row,"home_pitcher","home_probable_pitcher","home_starter",default="TBD")
    confirmed=_confirmed_flag(row)
    lineup_text="✅ LINEUPS CONFIRMED" if confirmed else "🕒 LINEUPS PENDING"
    gamepk=_txt(row,"game_pk","gamePk",default="—")
    st.markdown(f'''
<div class="dgp-game">
 <div class="dgp-top"><div class="dgp-num">GAME {idx} • MLB GAME ID { _esc(gamepk) }</div><div class="dgp-state">{_esc(lineup_text)}</div></div>
 <div class="dgp-match">
  <div class="dgp-team"><img src="{_esc(_logo(away_id))}">{_esc(away)}</div>
  <div class="dgp-at">@</div>
  <div class="dgp-team"><img src="{_esc(_logo(home_id))}">{_esc(home)}</div>
 </div>
 <div class="dgp-meta">{_esc(time)} ET • {_esc(venue)} • {_esc(status)}</div>
 <div class="dgp-starters">
  <div class="dgp-start"><span>Away probable starter</span><b>{_esc(away_sp)}</b></div>
  <div class="dgp-start"><span>Home probable starter</span><b>{_esc(home_sp)}</b></div>
 </div>
 <div class="dgp-slots">
  <div class="dgp-slot"><div class="dgp-slotnum">🥇 PICK 1</div><div class="dgp-empty">Waiting for Step 2</div><div class="dgp-wait">No market or player has been ranked yet.</div></div>
  <div class="dgp-slot"><div class="dgp-slotnum">🥈 PICK 2</div><div class="dgp-empty">Waiting for Step 2</div><div class="dgp-wait">No market or player has been ranked yet.</div></div>
  <div class="dgp-slot"><div class="dgp-slotnum">🥉 PICK 3</div><div class="dgp-empty">Waiting for Step 2</div><div class="dgp-wait">No market or player has been ranked yet.</div></div>
 </div>
</div>''',unsafe_allow_html=True)


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    _css()
    if games_df is None or games_df.empty:
        st.info("No verified MLB games are available for the selected date.")
        return
    frame=_sort_games(games_df)
    day=_txt(frame.iloc[0],"game_date",default="")[:10]
    verified=0
    if "game_pk" in frame.columns:
        try:
            verified=int((pd.to_numeric(frame["game_pk"],errors="coerce")>0).sum())
        except Exception:
            verified=len(frame)
    else:
        verified=len(frame)
    st.markdown(f'''<div class="dgp-hero"><div class="dgp-kicker">KYRE SPORTS AI • DAILY GAME PICKS • STEP 1</div><div class="dgp-title">🏆 Top 3 Picks — Every MLB Game</div><div class="dgp-sub">Foundation first: every verified matchup for the selected slate is shown below with official game identity, teams, start time, venue, probable starters and lineup state. The three pick slots intentionally remain empty until Step 2 connects eligible markets.</div></div>''',unsafe_allow_html=True)
    st.success(f"✅ Verified slate shell ready • {day or 'selected date'} • {verified}/{len(frame)} games with official MLB IDs • 0 picks generated")
    for i,(_,row) in enumerate(frame.iterrows(),1):
        _render_game(row,i)
    st.markdown(f'<div class="dgp-foot">{VERSION} • verified-slate presentation layer only • no ranking/projection logic active • existing market engines unchanged</div>',unsafe_allow_html=True)
