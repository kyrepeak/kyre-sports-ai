"""MLB Daily Rankings V1.2 — V1.1 matchup calibration + verified environment intelligence.

Adds runtime-verified venue/weather context on top of V1.1. Weather is fetched
only when MLB provides usable venue coordinates and Open-Meteo returns a valid
hourly forecast near first pitch. Effects are deliberately tiny and capped.
Bullpen and advanced Statcast enrichments remain explicitly pending unless a
verified feed is available; nothing is fabricated.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
import streamlit as st

import mlb_matchup_rankings_v11 as base
import mlb_matchup_hub_v10 as ui
from engine import odds

VERSION = "MLB Daily Rankings V1.2"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


@st.cache_data(ttl=1800, show_spinner=False)
def _venue_environment(game_pk):
    """Return verified venue coordinates + nearest-hour weather when available."""
    out={"weather_status":"PENDING","venue_status":"PENDING"}
    try:
        d=ui._json(f"{ui.MLB_API}/schedule", {
            "sportId":1,"gamePk":int(game_pk),"hydrate":"venue(location)"
        })
        dates=d.get("dates") or []
        game=((dates[0].get("games") or [])[0]) if dates and (dates[0].get("games") or []) else {}
        venue=game.get("venue") or {}
        out["venue_name"]=venue.get("name") or "—"
        loc=venue.get("location") or {}
        lat=_finite(loc.get("defaultCoordinates",{}).get("latitude") if isinstance(loc.get("defaultCoordinates"),dict) else None)
        lon=_finite(loc.get("defaultCoordinates",{}).get("longitude") if isinstance(loc.get("defaultCoordinates"),dict) else None)
        # Some MLB responses expose coordinates directly.
        if lat is None: lat=_finite(loc.get("latitude"))
        if lon is None: lon=_finite(loc.get("longitude"))
        game_time=game.get("gameDate")
        out["venue_status"]="VERIFIED" if lat is not None and lon is not None else "VENUE VERIFIED • COORDS PENDING"
        out["lat"],out["lon"],out["game_time"]=lat,lon,game_time
        if lat is None or lon is None:
            return out

        wx=ui._json("https://api.open-meteo.com/v1/forecast", {
            "latitude":lat,"longitude":lon,
            "hourly":"temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m",
            "temperature_unit":"fahrenheit","wind_speed_unit":"mph","timezone":"UTC","forecast_days":3
        })
        hourly=wx.get("hourly") or {}; times=hourly.get("time") or []
        if not times: return out
        target=None
        try:
            target=datetime.fromisoformat(str(game_time).replace("Z","+00:00"))
        except Exception:
            target=datetime.now(timezone.utc)
        best=min(range(len(times)),key=lambda i:abs((datetime.fromisoformat(str(times[i])).replace(tzinfo=timezone.utc)-target).total_seconds()))
        def arr(name):
            a=hourly.get(name) or []
            return _finite(a[best]) if best < len(a) else None
        out.update({
            "weather_status":"VERIFIED",
            "temp_f":arr("temperature_2m"),
            "precip_pct":arr("precipitation_probability"),
            "wind_mph":arr("wind_speed_10m"),
            "gust_mph":arr("wind_gusts_10m"),
        })
    except Exception:
        pass
    return out


def _environment_adjust(row, market):
    env=_venue_environment(row.get("game_pk")) if row.get("game_pk") else {"weather_status":"PENDING"}
    adj=0.0; reasons=[]
    # Weather is a small contextual modifier only. Direction is unavailable here,
    # so wind speed never receives a positive HR/hit boost by itself.
    if env.get("weather_status")=="VERIFIED":
        temp=env.get("temp_f"); precip=env.get("precip_pct"); wind=env.get("wind_mph")
        if temp is not None:
            # Warm/cold air adjustment, hard-capped to ±0.45 pp.
            t=max(-1.0,min(1.0,(temp-72.0)/22.0))
            scale=.0045 if market in ("Home Run","Total Bases","H+R+RBI") else .0025
            a=t*scale; adj+=a; reasons.append(f"{temp:.0f}°F")
        if precip is not None and precip>=45:
            # Uncertain wet conditions lower confidence slightly rather than
            # pretending to know delay/roof behavior.
            a=-.0015 if market in ("1+ Hit","Total Bases","Home Run") else -.001
            adj+=a; reasons.append(f"Precip {precip:.0f}%")
        if wind is not None and wind>=18:
            # No wind direction -> no directional performance boost.
            reasons.append(f"Wind {wind:.0f} mph (direction unavailable)")
    adj=max(-.008,min(.008,adj))
    return adj,{**env,"environment_adj":adj,"environment_reasons":reasons,
               "bullpen_layer":"PENDING","statcast_layer":"PENDING","pitch_mix_layer":"PENDING"}


def scan_market(games_df, market, sims=20_000, include_live=False):
    rows,diag=base.scan_market(games_df,market,sims,include_live)
    for r in rows:
        env_adj,env=_environment_adjust(r,market)
        rel=float(r.get("reliability") or 0)
        applied=env_adj*(0.65+0.35*rel)
        r["pre_environment_p"]=float(r.get("p") or 0)
        r["p"]=max(.001,min(.999,r["pre_environment_p"]+applied))
        r.update(env)
        r["applied_environment_adj"]=applied
    rows.sort(key=lambda x:(x["p"],x.get("reliability",0),1 if x.get("confirmed") else 0),reverse=True)
    diag=dict(diag); diag["environment_version"]="V1.2"
    return rows,diag


def _render_top5(rows,market,sims):
    top=rows[:5]
    if not top:
        st.warning("No eligible hitters were successfully modeled for this market."); return
    cards=[]
    for i,r in enumerate(top,1):
        status="✅ CONFIRMED" if r.get("confirmed") else "🕒 PROJECTED"
        fair=odds(r["p"])
        starter=f"{r.get('starter','TBD')} ({r.get('starter_hand','—')})"
        starter_bits=[]
        if r.get("starter_era") is not None: starter_bits.append(f"ERA {r['starter_era']:.2f}")
        if r.get("starter_k9") is not None: starter_bits.append(f"K/9 {r['starter_k9']:.1f}")
        ctx_shift=float(r.get("applied_context_adj") or 0)*100
        env_shift=float(r.get("applied_environment_adj") or 0)*100
        if r.get("weather_status")=="VERIFIED":
            wx=[]
            if r.get("temp_f") is not None: wx.append(f"{r['temp_f']:.0f}°F")
            if r.get("wind_mph") is not None: wx.append(f"Wind {r['wind_mph']:.0f} mph")
            if r.get("precip_pct") is not None: wx.append(f"Precip {r['precip_pct']:.0f}%")
            wx_text=" • ".join(wx) or "verified"
        else:
            wx_text="pending"
        cards.append(f'''<div class="rk-card {'first' if i==1 else ''}"><div class="rk-rank">{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '•'} RANK {i} • {status}</div><div class="rk-name">{ui._esc(r['player'])}</div><div class="rk-match">{ui._esc(r['team'])} vs {ui._esc(r['opponent'])} • Bat #{ui._esc(r.get('bat_spot'))}</div><div class="rk-p">{r['p']*100:.1f}%</div><div class="rk-label">{ui._esc(market)} probability • Fair {ui._esc(fair)}</div><div class="rk-details">{ui._esc(r['support'])}</div><div class="rk-details">⚾ vs {ui._esc(starter)} • {' • '.join(starter_bits) if starter_bits else 'starter stats pending'} • Matchup {ctx_shift:+.1f} pts</div><div class="rk-details">🌦️ {ui._esc(r.get('venue_name') or r.get('venue') or 'Venue')} • {ui._esc(wx_text)} • Environment {env_shift:+.1f} pts</div><div class="rk-badges"><span class="rk-pill good">{ui._esc(r['confidence'])}</span><span class="rk-pill">Reliability {r['reliability']*100:.0f}%</span><span class="rk-pill">{r['sample']:.0f} {ui._esc(r['sample_unit'])}</span></div></div>''')
    st.markdown(f'<div class="rk-grid">{"".join(cards)}</div>',unsafe_allow_html=True)
    st.caption(f"{VERSION} • {int(sims):,} simulations/hitter • V1.1 matchup context + verified weather environment • total context remains tightly capped • sportsbook prices excluded from model inputs.")
    st.info("🧪 Advanced Statcast contact quality, pitch-mix compatibility and bullpen-fatigue layers remain PENDING until their verified feeds are connected. They are not assigned synthetic values.")


def render_daily_rankings(games_df):
    base.base._css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings — Environment Intelligence</div><div class="rk-sub">Frozen production engines + sample calibration + starter/lineup context + verified weather when available</div></div><div class="rk-sub">V1.2</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:
        st.info("No verified MLB slate is available for rankings."); return
    market=st.selectbox("RANKING MARKET",base.base.MARKETS,key="mx_rank_market_v12")
    c1,c2=st.columns([2,1])
    with c1:
        depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],index=1,format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth_v12")
    with c2:
        include_live=st.checkbox("Include live games",value=False,key="mx_rank_live_v12")
    day=str(games_df.iloc[0].get("game_date"))[:10]
    key=f"mx_rank_v12::{day}::{market}::{depth}::{int(include_live)}"
    if st.button(f"🔥 BUILD ENVIRONMENT-CALIBRATED TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_build_v12"):
        with st.spinner(f"Scanning {market} slate + matchup/environment intelligence..."):
            rows,diag=scan_market(games_df,market,depth,include_live)
            st.session_state[key]={"rows":rows,"diag":diag}
    result=st.session_state.get(key)
    if result:
        d=result["diag"]
        st.success(f"✅ {d['modeled']}/{d['pool']} eligible hitters modeled • {d['errors']} profile errors • matchup + verified environment layer checked")
        _render_top5(result["rows"],market,depth)
    else:
        st.info("Choose a market and build the Top 5. The enriched scan runs only on demand.")
