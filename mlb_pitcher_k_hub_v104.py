"""MLB Pitcher Strikeouts O/U V1.0.4 — prop-feed parser hardening."""
from __future__ import annotations
import requests
import streamlit as st
import mlb_pitcher_k_hub_v103 as v103
import mlb_pitcher_k_hub_v102 as oddsbridge
engine = oddsbridge.base
MODEL_VERSION = "Pitcher K V1.0.4"

def _desc(m):
    m=m or {}
    return " ".join(str(m.get(k) or "") for k in ("name","label","key","type")).strip()

def _is_k_market(m):
    t=" ".join(_desc(m).lower().replace("_"," ").replace("/"," ").split())
    return "strikeout" in t or ("pitcher" in t and (" k " in f" {t} " or "ks" in t))

def _player_label(row, market):
    vals=[row.get("label"),row.get("name"),row.get("playerName"),row.get("player_name"),row.get("participantName"),row.get("description"),market.get("playerName"),market.get("player_name")]
    p=row.get("participant") or market.get("participant")
    if isinstance(p,dict): vals += [p.get("name"),p.get("displayName")]
    for v in vals:
        s=str(v or "").strip()
        if s and s.lower() not in {"over","under","o","u"}: return s
    return ""

def _parse_props(payload, pitcher_names):
    wanted={engine._norm_name(x):x for x in pitcher_names if x}
    out={x:[] for x in wanted.values()}
    books=(payload or {}).get("bookmakers") or {}
    if not isinstance(books,dict): return out
    for book,markets in books.items():
        if isinstance(markets,dict): markets=list(markets.values())
        for market in markets or []:
            if not isinstance(market,dict) or not _is_k_market(market): continue
            for row in market.get("odds") or market.get("outcomes") or []:
                if not isinstance(row,dict): continue
                norm=engine._norm_name(_player_label(row,market)); match=None
                for wn,orig in wanted.items():
                    if wn and norm and (wn==norm or wn in norm or norm in wn): match=orig; break
                if not match: continue
                line=None
                for f in ("hdp","line","total","points","threshold","max"):
                    line=engine.sf(row.get(f))
                    if line is not None: break
                if line is None:
                    for f in ("hdp","line","total","points","threshold"):
                        line=engine.sf(market.get(f))
                        if line is not None: break
                if line is None: continue
                over=engine.sf(row.get("over")); under=engine.sf(row.get("under"))
                for o in row.get("outcomes") or []:
                    if not isinstance(o,dict): continue
                    side=str(o.get("name") or o.get("label") or "").lower(); price=engine.sf(o.get("price") or o.get("odds") or o.get("decimal"))
                    if "over" in side and over is None: over=price
                    if "under" in side and under is None: under=price
                out[match].append({"book":str(book),"line":float(line),"over_dec":over,"under_dec":under,"updatedAt":market.get("updatedAt")})
    return out

def _payloads(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        if isinstance(data.get("data"),list): return data["data"]
        if data.get("id") is not None: return [data]
    return []

def _market_names(payload):
    names=[]
    for book,markets in ((payload or {}).get("bookmakers") or {}).items():
        if isinstance(markets,dict): markets=list(markets.values())
        for m in markets or []:
            if isinstance(m,dict) and _desc(m): names.append(f"{book}: {_desc(m)}")
    return names

def _fetch(games_df,pitcher_rows):
    key=oddsbridge.get_api_key() or ""; books=oddsbridge.get_bookmakers()
    if not key or games_df is None or games_df.empty: return {},{"connected":False,"events":0,"props":0,"books":books}
    try:
        start,end=oddsbridge._window_for_games(games_df); events=oddsbridge.fetch_mlb_events(key,start,end)
    except Exception as exc: return {},{"connected":False,"events":0,"props":0,"error":str(exc),"books":books}
    match={}; ids=[]
    for _,row in games_df.iterrows():
        try: pk=int(row.get("game_pk"))
        except Exception: continue
        e=oddsbridge._match_event(events,row)
        if e and e.get("id") is not None: match[pk]=e; ids.append(e.get("id"))
    payload_map={}; seen=[]
    try:
        for p in oddsbridge.fetch_multi_odds(key,tuple(ids),books):
            if isinstance(p,dict) and p.get("id") is not None: payload_map[str(p.get("id"))]=p; seen += _market_names(p)
    except Exception: pass
    for eid in ids:
        try:
            r=requests.get(f"{oddsbridge.ODDS_BASE}/odds",params={"apiKey":str(key),"eventId":str(eid),"bookmakers":str(books)},timeout=15)
            if r.status_code>=400: continue
            for p in _payloads(r.json()):
                if p.get("id") is not None: payload_map[str(p.get("id"))]=p; seen += _market_names(p)
        except Exception: continue
    out={}; count=0
    for pk,e in match.items():
        p=payload_map.get(str(e.get("id")))
        if not p: continue
        names=[x.get("player_name") for x in pitcher_rows if int(x.get("game_pk",-1))==pk]
        for name,quotes in _parse_props(p,names).items():
            board=engine._market_board(quotes)
            if board: out[(pk,engine._norm_name(name))]=board; count+=1
    uniq=[]
    for x in seen:
        if x not in uniq: uniq.append(x)
    return out,{"connected":True,"events":len(match),"props":count,"books":books,"market_names":uniq[:80]}

engine._parse_props=_parse_props
engine._fetch_market_lines=_fetch

def render_pitcher_k_hub(games_df,section_header,status_info,team_logo,h):
    result=v103.render_pitcher_k_hub(games_df,section_header,status_info,team_logo,h)
    meta=st.session_state.get("pk10_market_meta") or {}
    if meta.get("connected") and int(meta.get("props") or 0)==0:
        names=meta.get("market_names") or []
        if names:
            with st.expander("🔎 Pitcher-prop feed diagnostic",expanded=False):
                st.code("\n".join(names[:80]))
        else:
            st.caption("Odds provider matched the games but returned no market names for the selected DraftKings/FanDuel event payloads.")
    return result
