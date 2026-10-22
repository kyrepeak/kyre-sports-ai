"""Kyre Sports API — adaptive CFB Top Picks Page 2 Analytics Lab V1."""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping, Sequence
from fastapi import APIRouter, Query

import cfb_over_under_model_v1 as total_model
import cfb_player_props_fanduel_bound_v2 as fanduel_props
import cfb_player_props_odds_api_v1 as odds_props
import sports_api.api.cfb_game_total_page1_v1 as game_api
import sports_api.api.cfb_moneyline_page1_v1 as ml_api
import sports_api.api.cfb_top_picks_page1_v3 as page1_math
import sports_api.api.cfb_top_picks_page1_v4 as page1_v4

router=APIRouter(prefix="/api/v1/cfb/top-picks",tags=["cfb"])
MODEL_VERSION="CFB TOP PICKS PAGE2 API V1 • ADAPTIVE ANALYTICS LAB"
SCHEMA_VERSION="cfb_top_picks_page2_v1"
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
MAY_MODIFY_PROJECTION=False
FORBIDDEN_PROVIDERS=("SGO","ESPN","ESPN BET")
STATUSES={"READY","PARTIAL","DATA_UNAVAILABLE","NOT_APPLICABLE","SOURCE_DEGRADED","IDENTITY_UNAVAILABLE"}
MODULES=("kyre_verdict","line_lab","projection","drivers","matchup","recent_form","history","market_board","line_movement","availability","game_environment","risks","flip_conditions","sources")

def _c(v:Any)->str:return str(v or "").strip()
def _n(v:Any)->float|None:
    if v is None or isinstance(v,bool):return None
    try:x=float(v)
    except (TypeError,ValueError,OverflowError):return None
    return x if math.isfinite(x) else None

def _m(status="DATA_UNAVAILABLE",**kw):return {"status":status,**kw}
def _day(s:Mapping[str,Any])->str:
    if _c(s.get("selected_date")):return _c(s.get("selected_date"))
    return _c(s.get("kickoff_iso"))[:10]

def resolve_candidate(candidate_id:str,kind:str|None=None,game_date:str|None=None)->dict[str,Any]:
    payload=page1_v4.build_page1_payload(game_date=game_date,limit=10)
    rows=list(payload.get("game_picks") or [])+list(payload.get("player_props") or [])
    exact=[dict(r) for r in rows if _c(r.get("candidate_id"))==_c(candidate_id)]
    if kind:exact=[r for r in exact if ("player-prop" if r.get("player_name") else "game-pick")==kind]
    if len(exact)!=1:return {"status":"IDENTITY_UNAVAILABLE","selection_snapshot":None,"reason":"Exact Page 1 candidate was not uniquely resolved."}
    row=exact[0]; row["kind"]="player-prop" if row.get("player_name") else "game-pick"; row["selected_date"]=_c(payload.get("selected_date") or game_date or _day(row))
    return {"status":"READY","selection_snapshot":row,"page1_schema":payload.get("schema_version")}

def _game_context(s:Mapping[str,Any])->tuple[dict[str,Any],dict[str,Any]]:
    day=_day(s); eid=_c(s.get("event_id") or s.get("official_game_id"))
    games=game_api._load_ncaa_games(day)
    matches=[dict(g) for g in games if _c(g.get("game_id") or g.get("identity_key"))==eid]
    if len(matches)!=1:return {},{}
    game=matches[0]
    try:analysis=dict(ml_api._analysis(game,day) or {})
    except Exception:analysis={}
    return game,analysis

def _stat(profile:Mapping[str,Any],key:str)->float|None:
    raw=(profile.get("official_stats") or {}).get(key) or {}
    return _n(raw.get("value_numeric") if isinstance(raw,Mapping) else raw)

def _game_analysis(s:Mapping[str,Any])->dict[str,Any]:
    game,a=_game_context(s)
    if not game:return {k:_m("DATA_UNAVAILABLE") for k in ("projection","drivers","matchup","recent_form","history","game_environment","risks","flip_conditions")}|{"line_scenarios":[],"sources":_m("DATA_UNAVAILABLE")}
    final=dict(a.get("final") or {}); away=dict(a.get("away") or {}); home=dict(a.get("home") or {})
    ph=_n(final.get("projected_home_points")); pa=_n(final.get("projected_away_points")); margin=_n(final.get("projected_margin_home")); total=_n(final.get("projected_total")); p=_n(s.get("probability"))
    projection=_m("READY" if final.get("ready") else "PARTIAL",projected_home_points=ph,projected_away_points=pa,projected_margin_home=margin,projected_total=total,selected_probability=p,reliability=final.get("reliability"),model_owner="Kyre certified CFB model")
    drivers=[]
    for title,key in (("Scoring offense","scoring_offense"),("Total offense","total_offense"),("Scoring defense","scoring_defense"),("Total defense","total_defense"),("Turnover margin","turnover_margin")):
        av,hv=_stat(away,key),_stat(home,key)
        if av is not None or hv is not None:drivers.append({"title":title,"away":av,"home":hv,"source":"NCAA official team stats"})
    matchup=_m("READY" if drivers else "DATA_UNAVAILABLE",rows=drivers,away_team=s.get("away_team"),home_team=s.get("home_team"))
    market=_c(s.get("market_type")).upper(); selected=_n(s.get("line")); side=_c(s.get("side")).upper(); scenarios=[]
    if selected is not None and market=="SPREAD" and margin is not None and side in {"HOME","AWAY"}:
        for line in (selected-4,selected-2,selected,selected+2,selected+4):scenarios.append({"line":round(line,1),"selected_side_probability":page1_math._spread_probability(margin,line,home_side=side=="HOME"),"model_owner":"Kyre certified CFB spread distribution"})
    elif selected is not None and market=="TOTAL":
        for line in (selected-4,selected-2,selected,selected+2,selected+4):
            try:r=total_model.project_matchup(game,away,home,line)
            except Exception:continue
            if r.get("ready") is True:scenarios.append({"line":round(line,1),"over_probability":_n(r.get("over_probability")),"under_probability":_n(r.get("under_probability")),"model_owner":"Kyre certified CFB total model"})
    risks=[]
    if final.get("reliability") is not None:risks.append({"title":"Model reliability","value":final.get("reliability")})
    flips=[]
    if market=="SPREAD" and selected is not None:flips.append({"title":"Spread threshold","text":f"Recheck if the selected line moves materially away from {selected:+g}."})
    if market=="TOTAL" and selected is not None:flips.append({"title":"Total threshold","text":f"Recheck if the total moves materially away from {selected:g}."})
    return {"projection":projection,"drivers":_m("READY" if drivers else "DATA_UNAVAILABLE",items=drivers),"matchup":matchup,"recent_form":_m("DATA_UNAVAILABLE",reason="No separate approved recent-form module is attached to this selection."),"history":_m("DATA_UNAVAILABLE",reason="No head-to-head history is required to render this pick."),"game_environment":_m("PARTIAL",kickoff=s.get("kickoff_iso"),source="NCAA verified schedule"),"risks":_m("READY",items=risks),"flip_conditions":_m("READY",items=flips),"line_scenarios":scenarios,"sources":_m("READY",sources=[{"provider":"NCAA","role":"identity + official team stats"},{"provider":"Kyre certified CFB model","role":"projection + probabilities"}])}

def _prop_analysis(s:Mapping[str,Any])->dict[str,Any]:
    game,a=_game_context(s); home=dict(a.get("home") or {}); away=dict(a.get("away") or {})
    team=_c(s.get("player_team")); opp=_c(s.get("opponent")); opp_profile=home if _c(home.get("team"))==opp else away if _c(away.get("team"))==opp else {}
    items=[]
    for title,key in (("Opponent total defense","total_defense"),("Opponent scoring defense","scoring_defense")):
        value=_stat(opp_profile,key)
        if value is not None:items.append({"title":title,"value":value,"source":"NCAA official team stats"})
    identity_ok=_c(s.get("player_identity_status"))=="VERIFIED" or bool(_c(s.get("player_id")))
    return {"projection":_m("PARTIAL",selected_hit_probability=_n(s.get("probability")),projected_stat=None,reason="Page 1 hit probability is preserved; a clean approved player-history projection provider is not configured."),"drivers":_m("READY" if items else "DATA_UNAVAILABLE",items=items),"matchup":_m("READY" if game else "DATA_UNAVAILABLE",player_team=team,opponent=opp,items=items,source="NCAA"),"recent_form":_m("DATA_UNAVAILABLE",rows=[],reason="Approved player game-log provider not configured."),"history":_m("DATA_UNAVAILABLE",rows=[],reason="Approved player history provider not configured."),"game_environment":_m("PARTIAL",kickoff=s.get("kickoff_iso"),source="NCAA verified schedule"),"risks":_m("READY",items=[{"title":"Player-history coverage","value":"Limited until an approved clean provider is connected."}]),"flip_conditions":_m("READY",items=[{"title":"Availability","text":"Recheck if official availability changes before kickoff."}]),"line_scenarios":[],"sources":_m("READY" if identity_ok else "PARTIAL",sources=[{"provider":"Official team athletics roster","role":"current player identity"},{"provider":"NCAA","role":"game + opponent context"},{"provider":"Kyre Page 1 model","role":"selected hit probability"}])}

def _quote_from_snapshot(s:Mapping[str,Any])->dict[str,Any]:
    return {"sportsbook":_c(s.get("sportsbook")),"market":_c(s.get("market_type") or s.get("market_key")),"side":_c(s.get("side")),"selection":_c(s.get("selection")),"line":s.get("line"),"american_odds":s.get("american_odds"),"observed_at_utc":s.get("market_timestamp"),"source_provider":_c(s.get("source_provider") or s.get("sportsbook"))}

def _market(s:Mapping[str,Any])->dict[str,Any]:
    quotes=[_quote_from_snapshot(s)]; movement=_m("DATA_UNAVAILABLE",reason="Opening/current movement requires two same-book observations for the same market identity.")
    if s.get("kind")=="player-prop":
        game={"game_id":s.get("event_id"),"official_game_id":s.get("event_id"),"away_team":s.get("away_team"),"home_team":s.get("home_team"),"kickoff_iso":s.get("kickoff_iso")}
        for fetch in (fanduel_props.fetch_fanduel_cfb_player_props,odds_props.fetch_odds_api_cfb_player_props):
            try:rows=fetch([game])
            except Exception:rows=[]
            for r in rows:
                if _c(r.get("player_name")).casefold()!=_c(s.get("player_name")).casefold() or _c(r.get("stat_id") or r.get("market_key")).casefold()!=_c(s.get("market_key")).casefold():continue
                quotes.append({"sportsbook":_c(r.get("sportsbook")),"market":_c(r.get("stat_id") or r.get("market_key")),"side":_c(r.get("side")),"selection":None,"line":r.get("line"),"american_odds":r.get("price"),"observed_at_utc":r.get("observed_at_utc"),"source_provider":_c(r.get("source_provider") or r.get("sportsbook"))})
    else:
        game,_=_game_context(s)
        if game:
            try:matched,_=game_api._market_state([game]); raw=matched.get(_c(game.get("game_id") or game.get("identity_key")),[])
            except Exception:raw=[]
            mt=_c(s.get("market_type")).upper(); side=_c(s.get("side")).upper()
            for r in raw:
                book=_c(r.get("sportsbook")); stamp=r.get("observed_at_utc")
                if mt=="MONEYLINE":
                    val=r.get("home_moneyline") if side=="HOME" else r.get("away_moneyline"); line=None
                elif mt=="SPREAD":
                    val=r.get("home_spread_price") if side=="HOME" else r.get("away_spread_price"); line=r.get("home_spread") if side=="HOME" else r.get("away_spread")
                else:
                    val=r.get("over_price") if side=="OVER" else r.get("under_price"); line=r.get("total_line")
                if val is not None:quotes.append({"sportsbook":book,"market":mt,"side":side,"selection":None,"line":line,"american_odds":val,"observed_at_utc":stamp,"source_provider":_c(r.get("source_provider") or book)})
    chosen={}
    for q in quotes:
        key=(_c(q.get("sportsbook")),_c(q.get("market")).casefold(),_c(q.get("side")).casefold(),q.get("line"))
        chosen[key]=q
    rows=list(chosen.values()); selected_line=s.get("line"); comparable=[q for q in rows if q.get("line")==selected_line or selected_line is None]
    def score(q):
        x=_n(q.get("american_odds")); return -999999 if x is None else x
    best=max(comparable,key=score) if comparable else None
    return {"market_board":_m("READY" if rows else "DATA_UNAVAILABLE",quotes=rows,best_available_price=best),"line_movement":movement}

def _implied(price:Any)->float|None:
    p=_n(price)
    if p is None or p==0 or (-100<p<100):return None
    return (-p)/((-p)+100) if p<0 else 100/(p+100)
def _fair(prob:Any)->int|None:
    p=_n(prob)
    if p is None or p<=0 or p>=1:return None
    return int(round(-100*p/(1-p))) if p>=.5 else int(round(100*(1-p)/p))
def _decision(s:Mapping[str,Any],analysis:Mapping[str,Any])->dict[str,Any]:
    p=_n(s.get("probability")); imp=_implied(s.get("american_odds")); edge=None if p is None or imp is None else p-imp
    verdict="DATA UNAVAILABLE" if edge is None else "BETTABLE EDGE" if edge>=.03 else "WATCH" if edge>=0 else "PASS AT THIS PRICE"
    v=_m("READY" if p is not None else "DATA_UNAVAILABLE",outcome_confidence=p,market_implied_probability=imp,market_value_edge=edge,model_fair_price=_fair(p),selected_price=s.get("american_odds"),verdict=verdict)
    mt=_c(s.get("market_type")).upper(); scenarios=list(analysis.get("line_scenarios") or [])
    if mt=="MONEYLINE" and p is not None:
        selected=int(s.get("american_odds") or -110); prices=sorted(set((selected-100,selected-50,selected,selected+50,selected+100)))
        lab=_m("READY",lab_type="PRICE",scenarios=[{"american_odds":x,"implied_probability":_implied(x),"model_probability":p,"market_value_edge":p-_implied(x)} for x in prices if _implied(x) is not None])
    elif scenarios:lab=_m("READY",lab_type="LINE",scenarios=scenarios)
    else:lab=_m("DATA_UNAVAILABLE",lab_type="LINE",scenarios=[],reason="No certified alternate-line scenarios are available for this market family.")
    return {"kyre_verdict":v,"line_lab":lab}

def _availability(s:Mapping[str,Any])->dict[str,Any]:
    status=_c(s.get("availability_status")); source=_c(s.get("availability_source")); stamp=_c(s.get("availability_observed_at"))
    approved=source.casefold().startswith(("official team","official conference","rotowire","sportsdataio")) if source else False
    return _m("READY",player_status=status,source=source,observed_at=stamp) if status and approved and stamp else _m("DATA_UNAVAILABLE",reason="No approved fresh availability observation is attached to this selection.")

def build_page2_payload(candidate_id:str,kind:str|None=None,game_date:str|None=None)->dict[str,Any]:
    resolved=resolve_candidate(candidate_id,kind,game_date)
    if resolved["status"]!="READY":return {"service":"Kyre Sports API","schema_version":SCHEMA_VERSION,"model_version":MODEL_VERSION,"identity":resolved,**{k:_m("IDENTITY_UNAVAILABLE") for k in MODULES}}
    s=dict(resolved["selection_snapshot"]); analysis=_prop_analysis(s) if s["kind"]=="player-prop" else _game_analysis(s)
    market=_market(s); decision=_decision(s,analysis); availability=_availability(s) if s["kind"]=="player-prop" else _m("NOT_APPLICABLE")
    out={"service":"Kyre Sports API","schema_version":SCHEMA_VERSION,"model_version":MODEL_VERSION,"selection_snapshot":s,"identity":resolved,**decision,**market,"availability":availability}
    for k in ("projection","drivers","matchup","recent_form","history","game_environment","risks","flip_conditions"):out[k]=analysis.get(k,_m())
    out["sources"]=_m("READY",modules={k:out[k].get("status") for k in MODULES if isinstance(out.get(k),Mapping)},source_contract=analysis.get("sources"),forbidden_providers=list(FORBIDDEN_PROVIDERS),null_is_not_zero=True,sportsbook_projection_influence=0.0)
    return out

@router.get("/page2")
def get_page2(candidate_id:str=Query(...,min_length=1),kind:str|None=Query(default=None),game_date:str|None=Query(default=None))->dict[str,Any]:
    return build_page2_payload(candidate_id,kind,game_date)

__all__=["MODEL_VERSION","SCHEMA_VERSION","SPORTSBOOK_PROJECTION_INFLUENCE","build_page2_payload","resolve_candidate","router"]
