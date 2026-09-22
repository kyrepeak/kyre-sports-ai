"""MLB Daily Rankings V1.1 — verified matchup-context calibration.

Builds on V1.0 slate rankings while preserving frozen market engines. Applies
only verified/capped context adjustments: opposing starter quality, handedness
availability, lineup confirmation/batting slot, and sample reliability. Park,
weather, bullpen and Statcast layers are explicitly labeled pending when no
verified feed is connected; they are never fabricated.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_rankings_v10 as base
import mlb_matchup_hub_v10 as ui
from engine import odds

VERSION = "MLB Daily Rankings V1.1"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


@st.cache_data(ttl=300, show_spinner=False)
def _starter_profile(pid, season):
    if not pid:
        return {}
    try:
        person=ui._person(int(pid))
        hand=str((person.get("pitchHand") or {}).get("code") or "—")
        d=ui._json(f"{ui.MLB_API}/people/{int(pid)}/stats", {"stats":"season","group":"pitching","season":int(season)})
        blocks=d.get("stats") or []
        s=(blocks[0].get("splits") or [{}])[0].get("stat",{}) if blocks else {}
        ip=_finite(s.get("inningsPitched"),0) or 0
        so=_finite(s.get("strikeOuts"),0) or 0
        return {
            "hand":hand,
            "era":_finite(s.get("era")),
            "whip":_finite(s.get("whip")),
            "k9":_finite(s.get("strikeoutsPer9Inn")) or ((so*9/ip) if ip else None),
            "hr9":_finite(s.get("homeRunsPer9")),
        }
    except Exception:
        return {}


def _game_maps(games_df):
    out={}
    if games_df is None:
        return out
    for _,r in games_df.iterrows():
        try: pk=int(r.get("game_pk"))
        except Exception: continue
        out[pk]={
            "away_pitcher_id":r.get("away_pitcher_id"),"home_pitcher_id":r.get("home_pitcher_id"),
            "away_pitcher":r.get("away_pitcher"),"home_pitcher":r.get("home_pitcher"),
            "away_team":r.get("away_team"),"home_team":r.get("home_team"),
            "venue":r.get("venue"),
        }
    return out


def _context_adjust(row, games, year, market):
    """Return capped probability-point adjustment + audit fields."""
    g=games.get(int(row.get("game_pk") or 0),{})
    team=str(row.get("team") or "")
    is_away=(team==str(g.get("away_team") or ""))
    spid=g.get("home_pitcher_id") if is_away else g.get("away_pitcher_id")
    spname=g.get("home_pitcher") if is_away else g.get("away_pitcher")
    sp=_starter_profile(spid,year)
    adj=0.0; reasons=[]

    # Starter run-prevention quality: intentionally modest/capped.
    era=sp.get("era"); k9=sp.get("k9"); hr9=sp.get("hr9")
    if era is not None:
        era_delta=max(-1.5,min(1.5,(4.20-era)/1.5))
        if market in ("1+ Hit","Total Bases","H+R+RBI"):
            a=-0.012*era_delta
        elif market=="Home Run":
            a=-0.008*era_delta
        else:
            a=-0.010*era_delta
        adj+=a; reasons.append(f"Starter ERA {era:.2f}")
    if k9 is not None and market in ("1+ Hit","Total Bases"):
        kd=max(-1.5,min(1.5,(k9-8.5)/2.0)); a=-0.006*kd; adj+=a
        reasons.append(f"K/9 {k9:.1f}")
    if hr9 is not None and market=="Home Run":
        hd=max(-1.5,min(1.5,(hr9-1.15)/.55)); a=0.012*hd; adj+=a
        reasons.append(f"HR/9 {hr9:.2f}")

    # Lineup certainty / PA opportunity. This is a ranking-confidence nudge only.
    confirmed=bool(row.get("confirmed")); spot=int(row.get("bat_spot") or 99)
    if confirmed:
        adj+=0.004
        reasons.append("Confirmed lineup")
    if spot<=2:
        adj+=0.005
        reasons.append(f"Bat #{spot}")
    elif spot>=7 and spot<99:
        adj-=0.004
        reasons.append(f"Bat #{spot}")

    # Hard cap: context refines, never replaces the production engine.
    adj=max(-0.035,min(0.035,adj))
    return adj,{
        "starter":str(spname or row.get("starter") or "TBD"),
        "starter_hand":sp.get("hand") or "—",
        "starter_era":era,"starter_k9":k9,"starter_hr9":hr9,
        "venue":g.get("venue") or "—",
        "context_reasons":reasons,
        "context_adj":adj,
        "park_layer":"PENDING",
        "weather_layer":"PENDING",
        "bullpen_layer":"PENDING",
        "statcast_layer":"ENGINE/FEED DEPENDENT",
    }


def scan_market(games_df, market, sims=20_000, include_live=False):
    rows,diag=base.scan_market(games_df,market,sims,include_live)
    year=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    gm=_game_maps(games_df)
    for r in rows:
        adj,ctx=_context_adjust(r,gm,year,market)
        raw=float(r.get("p") or 0)
        # Reliability dampens the context adjustment for thin samples.
        rel=float(r.get("reliability") or 0)
        applied=adj*(0.55+0.45*rel)
        r["pre_context_p"]=raw
        r["p"]=max(.001,min(.999,raw+applied))
        r.update(ctx)
        r["applied_context_adj"]=applied
    rows.sort(key=lambda x:(x["p"],x.get("reliability",0),1 if x.get("confirmed") else 0),reverse=True)
    diag=dict(diag); diag["context_version"]="V1.1"; diag["verified_context"]="starter + lineup + batting slot"
    return rows,diag


def _render_top5(rows,market,sims):
    top=rows[:5]
    if not top:
        st.warning("No eligible hitters were successfully modeled for this market."); return
    cards=[]
    for i,r in enumerate(top,1):
        status="✅ CONFIRMED" if r.get("confirmed") else "🕒 PROJECTED"
        fair=odds(r["p"])
        shift=(float(r.get("applied_context_adj") or 0)*100)
        starter=f"{r.get('starter','TBD')} ({r.get('starter_hand','—')})"
        starter_bits=[]
        if r.get("starter_era") is not None: starter_bits.append(f"ERA {r['starter_era']:.2f}")
        if r.get("starter_k9") is not None: starter_bits.append(f"K/9 {r['starter_k9']:.1f}")
        if market=="Home Run" and r.get("starter_hr9") is not None: starter_bits.append(f"HR/9 {r['starter_hr9']:.2f}")
        ctx=" • ".join(starter_bits) if starter_bits else "starter stats pending"
        cards.append(f'''<div class="rk-card {'first' if i==1 else ''}"><div class="rk-rank">{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '•'} RANK {i} • {status}</div><div class="rk-name">{ui._esc(r['player'])}</div><div class="rk-match">{ui._esc(r['team'])} vs {ui._esc(r['opponent'])} • Bat #{ui._esc(r.get('bat_spot'))}</div><div class="rk-p">{r['p']*100:.1f}%</div><div class="rk-label">{ui._esc(market)} probability • Fair {ui._esc(fair)}</div><div class="rk-details">{ui._esc(r['support'])}</div><div class="rk-details">⚾ vs {ui._esc(starter)} • {ui._esc(ctx)} • Context {shift:+.1f} pts</div><div class="rk-badges"><span class="rk-pill good">{ui._esc(r['confidence'])}</span><span class="rk-pill">Reliability {r['reliability']*100:.0f}%</span><span class="rk-pill">{r['sample']:.0f} {ui._esc(r['sample_unit'])}</span></div></div>''')
    st.markdown(f'<div class="rk-grid">{"".join(cards)}</div>',unsafe_allow_html=True)
    st.caption(f"{VERSION} • {int(sims):,} simulations per eligible hitter • verified starter/lineup context capped at ±3.5 probability points • sportsbook prices excluded from model inputs.")
    st.info("🌦️ Park/weather, bullpen and additional Statcast layers are not fabricated. They remain labeled pending until a verified feed is connected to the ranking engine.")


def render_daily_rankings(games_df):
    base._css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings — Matchup Calibrated</div><div class="rk-sub">Frozen production engines + sample calibration + verified starter/lineup context</div></div><div class="rk-sub">V1.1</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:
        st.info("No verified MLB slate is available for rankings."); return
    market=st.selectbox("RANKING MARKET",base.MARKETS,key="mx_rank_market_v11")
    c1,c2=st.columns([2,1])
    with c1:
        depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],index=1,format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth_v11")
    with c2:
        include_live=st.checkbox("Include live games",value=False,key="mx_rank_live_v11")
    day=str(games_df.iloc[0].get("game_date"))[:10]
    key=f"mx_rank_v11::{day}::{market}::{depth}::{int(include_live)}"
    if st.button(f"🔥 BUILD MATCHUP-CALIBRATED TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_build_v11"):
        with st.spinner(f"Scanning full {market} slate + verified matchup context..."):
            rows,diag=scan_market(games_df,market,depth,include_live)
            st.session_state[key]={"rows":rows,"diag":diag}
    result=st.session_state.get(key)
    if result:
        d=result["diag"]
        st.success(f"✅ {d['modeled']}/{d['pool']} eligible hitters modeled • {d['errors']} profile errors • starter/lineup context applied")
        _render_top5(result["rows"],market,depth)
    else:
        st.info("Choose a market and build the Top 5. The matchup-calibrated scan runs only on demand.")
