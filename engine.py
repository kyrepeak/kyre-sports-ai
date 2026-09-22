import re
from collections import Counter
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Kyre Sports AI", page_icon="🧠", layout="wide")
ET=ZoneInfo("America/New_York")
MLB_API="https://statsapi.mlb.com/api/v1"
LIVE_API="https://statsapi.mlb.com/api/v1.1"
SAVANT="https://baseballsavant.mlb.com"
HEADERS={"User-Agent":"Mozilla/5.0 KyreSportsAI/1.0"}

def season(): return datetime.now(ET).year
def sf(v,d=None):
    try:return float(v)
    except:return d
def clamp(v,a,b): return max(a,min(b,v))
def pct(v):
    x=sf(v)
    return None if x is None else x/100 if abs(x)>1 else x
def ipfloat(v):
    t=str(v or "0.0"); a,b=(t.split(".",1)+["0"])[:2]
    return (sf(a,0) or 0)+min(max(int(b[:1]) if b[:1].isdigit() else 0,0),2)/3
def ab_for_spot(n): return {1:4.6,2:4.5,3:4.4,4:4.3,5:4.2,6:4.1,7:4.0,8:3.9,9:3.8}.get(int(n or 4),4.1)
def odds(p):
    p=clamp(float(p),1e-6,1-1e-6)
    return f"{-100*p/(1-p):.0f}" if p>=.5 else f"+{100*(1-p)/p:.0f}"
def p_from_avg(avg,ab):
    avg=clamp(float(avg),0,.999); ab=max(float(ab),0)
    p0=(1-avg)**ab; p1=1-p0; one=clamp(ab*avg*((1-avg)**max(ab-1,0)),0,p1)
    return {"p_zero":p0,"p_one_plus":p1,"p_exact_one":one,"p_two_plus":max(0,p1-one),"expected_hits":avg*ab}
def combined(starter,bullpen,sab,bab):
    sab=max(float(sab),0); bab=max(float(bab),0); total=sab+bab
    p0=((1-clamp(starter,0,.999))**sab)*((1-clamp(bullpen,0,.999))**bab)
    eh=starter*sab+bullpen*bab; eff=eh/total if total else 0; sm=p_from_avg(eff,total)
    return {"p_zero":p0,"p_one_plus":1-p0,"p_exact_one":sm["p_exact_one"],"p_two_plus":sm["p_two_plus"],"expected_hits":eh,"effective_avg":eff}
def col(df,names):
    m={str(c).strip().lower():c for c in df.columns}
    for n in names:
        if n.lower() in m:return m[n.lower()]
def rowval(row,df,names,d=None):
    c=col(df,names)
    if c is None:return d
    v=row.get(c,d); return d if pd.isna(v) else v
def metric_grid(items,n=4):
    for i in range(0,len(items),n):
        chunk=items[i:i+n]; cs=st.columns(len(chunk))
        for c,it in zip(cs,chunk):
            with c: st.metric(it[0],it[1],delta=it[2] if len(it)>2 else None)
def actionable(status,include_live=False):
    s=str(status or "").lower()
    if any(x in s for x in ["final","game over","completed","cancel","postpon","suspended"]):return False
    if not include_live and any(x in s for x in ["in progress","live","delayed"]):return False
    return True

@st.cache_data(ttl=300)
def games_today():
    day=datetime.now(ET).strftime("%Y-%m-%d")
    r=requests.get(f"{MLB_API}/schedule",params={"sportId":1,"date":day,"hydrate":"probablePitcher,team"},timeout=15); r.raise_for_status()
    out=[]
    for block in r.json().get("dates",[]):
        for g in block.get("games",[]):
            a,h=g["teams"]["away"],g["teams"]["home"]; ap,hp=a.get("probablePitcher",{}),h.get("probablePitcher",{})
            t=datetime.fromisoformat(g["gameDate"].replace("Z","+00:00")).astimezone(ET)
            out.append({"game_pk":g.get("gamePk"),"venue_name":(g.get("venue") or {}).get("name","Unknown"),
                "away_team_id":a["team"].get("id"),"away_team":a["team"].get("name","Unknown"),
                "home_team_id":h["team"].get("id"),"home_team":h["team"].get("name","Unknown"),
                "away_pitcher_id":ap.get("id"),"away_pitcher":ap.get("fullName","TBD"),
                "home_pitcher_id":hp.get("id"),"home_pitcher":hp.get("fullName","TBD"),
                "first_pitch_et":t.strftime("%I:%M %p").lstrip("0"),"status":g.get("status",{}).get("detailedState","Unknown")})
    return pd.DataFrame(out),day

@st.cache_data(ttl=3600)
def player_search(name):
    r=requests.get(f"{MLB_API}/people/search",params={"names":name},timeout=15); r.raise_for_status()
    p=(r.json().get("people") or [None])[0]
    if not p:return None
    r=requests.get(f"{MLB_API}/people/{p['id']}",params={"hydrate":"currentTeam"},timeout=15); r.raise_for_status()
    p=(r.json().get("people") or [None])[0]
    if not p:return None
    team=p.get("currentTeam") or {}
    return {"id":p.get("id"),"name":p.get("fullName",name),"team_id":team.get("id"),"team_name":team.get("name","Unknown"),"bat_side":p.get("batSide",{}).get("code","?")}

@st.cache_data(ttl=600)
def hitter_stats(pid):
    r=requests.get(f"{MLB_API}/people/{pid}/stats",params={"stats":"season","group":"hitting","season":season()},timeout=15); r.raise_for_status()
    g=r.json().get("stats",[]); s=g[0]["splits"][0].get("stat",{}) if g and g[0].get("splits") else None
    if not s:return None
    return {"season":season(),"games":s.get("gamesPlayed",0),"plate_appearances":s.get("plateAppearances",0),"at_bats":s.get("atBats",0),
        "hits":s.get("hits",0),"home_runs":s.get("homeRuns",0),"walks":s.get("baseOnBalls",0),"strikeouts":s.get("strikeOuts",0),
        "avg":s.get("avg",".000"),"obp":s.get("obp",".000"),"slg":s.get("slg",".000"),"ops":s.get("ops",".000")}

@st.cache_data(ttl=600)
def pitcher_stats(pid):
    p=requests.get(f"{MLB_API}/people/{pid}",timeout=15); p.raise_for_status(); person=(p.json().get("people") or [{}])[0]
    r=requests.get(f"{MLB_API}/people/{pid}/stats",params={"stats":"season","group":"pitching","season":season()},timeout=15); r.raise_for_status()
    g=r.json().get("stats",[]); s=g[0]["splits"][0].get("stat",{}) if g and g[0].get("splits") else {}
    ips=s.get("inningsPitched","0.0"); ip=ipfloat(ips); k=sf(s.get("strikeOuts"),0) or 0
    return {"id":int(pid),"name":person.get("fullName","Unknown"),"hand":person.get("pitchHand",{}).get("code","?"),
        "era":s.get("era","N/A"),"whip":s.get("whip","N/A"),"wins":s.get("wins",0),"losses":s.get("losses",0),
        "games":int(sf(s.get("gamesPlayed"),0) or 0),"games_started":int(sf(s.get("gamesStarted"),0) or 0),
        "innings":ips,"true_innings":ip,"hits_allowed":sf(s.get("hits"),0) or 0,"walks":sf(s.get("baseOnBalls"),0) or 0,
        "earned_runs":sf(s.get("earnedRuns"),0) or 0,"strikeouts":k,"k9":k*9/ip if ip else None}

@st.cache_data(ttl=600)
def hand_split(pid,hand):
    hand=str(hand or "").upper()
    if hand not in {"R","L"}:return None
    sit="vr" if hand=="R" else "vl"
    for typ in ["statSplits","season"]:
        r=requests.get(f"{MLB_API}/people/{pid}/stats",params={"stats":typ,"group":"hitting","season":season(),"sitCodes":sit},timeout=15)
        if r.status_code>=400:continue
        for g in r.json().get("stats",[]):
            for sp in g.get("splits",[]):
                info=sp.get("split") or {}; desc=str(info.get("description","")).lower()
                ok=str(info.get("code","")).lower()==sit or (hand=="R" and "right" in desc) or (hand=="L" and "left" in desc)
                if typ=="statSplits" or ok:
                    s=sp.get("stat") or {}
                    if s:return {"label":"vs RHP" if hand=="R" else "vs LHP","at_bats":s.get("atBats",0),"hits":s.get("hits",0),
                        "home_runs":s.get("homeRuns",0),"strikeouts":s.get("strikeOuts",0),"avg":s.get("avg",".000"),
                        "obp":s.get("obp",".000"),"slg":s.get("slg",".000"),"ops":s.get("ops",".000")}

@st.cache_data(ttl=600)
def recent_form(pid,n=10):
    r=requests.get(f"{MLB_API}/people/{pid}/stats",params={"stats":"gameLog","group":"hitting","season":season()},timeout=15); r.raise_for_status()
    g=r.json().get("stats",[])
    if not g or not g[0].get("splits"):return None
    ab=h=hr=bb=so=hg=0; pks=[]
    splits=g[0]["splits"][-n:]
    for sp in splits:
        s=sp.get("stat") or {}; a=int(sf(s.get("atBats"),0) or 0); x=int(sf(s.get("hits"),0) or 0)
        ab+=a; h+=x; hr+=int(sf(s.get("homeRuns"),0) or 0); bb+=int(sf(s.get("baseOnBalls"),0) or 0); so+=int(sf(s.get("strikeOuts"),0) or 0); hg+=1 if x else 0
        pk=sp.get("game",{}).get("gamePk")
        if pk:pks.append(pk)
    return {"games":len(splits),"at_bats":ab,"hits":h,"home_runs":hr,"walks":bb,"strikeouts":so,"avg":h/ab if ab else None,"hit_games":hg,"game_pks":pks}

@st.cache_data(ttl=180)
def game_feed(pk):
    r=requests.get(f"{LIVE_API}/game/{int(pk)}/feed/live",timeout=20); r.raise_for_status(); return r.json()

@st.cache_data(ttl=180)
def environment(pk):
    p=game_feed(pk); gd=p.get("gameData",{}) or {}; v=gd.get("venue",{}) or {}; w=gd.get("weather",{}) or {}; f=v.get("fieldInfo",{}) or {}
    return {"venue_name":v.get("name","Unknown"),"roof_type":f.get("roofType","Unknown"),"temperature":sf(w.get("temp")),"condition":w.get("condition","Unknown"),"wind":w.get("wind","Unknown")}

@st.cache_data(ttl=180)
def lineup_snapshot(pk):
    p=game_feed(pk); box=p.get("liveData",{}).get("boxscore",{}).get("teams",{}) or {}; out={}
    for side in ("away","home"):
        t=box.get(side,{}) or {}; players=t.get("players",{}) or {}; order=[int(x) for x in t.get("battingOrder",[]) if str(x).isdigit()]; arr=[]
        for pos,pid in enumerate(order,1):
            o=players.get(f"ID{pid}",{}) or {}; person=o.get("person",{}) or {}; b=(o.get("seasonStats",{}) or {}).get("batting",{}) or {}
            arr.append({"player_id":pid,"player_name":person.get("fullName",f"Player {pid}"),"position":pos,"avg":b.get("avg"),"obp":b.get("obp"),"slg":b.get("slg"),"ops":b.get("ops"),"at_bats":b.get("atBats",0),"hits":b.get("hits",0)})
        out[side]=arr
    return out

@st.cache_data(ttl=180)
def lineup_position(pk,pid,side):
    snap=lineup_snapshot(pk)
    for p in snap.get(side,[]):
        if int(p["player_id"])==int(pid):return p["position"]

@st.cache_data(ttl=1800)
def recent_lineup_position(pid,pks,max_games=5):
    pos=[]
    for pk in list(pks)[-max_games:]:
        for side in ("home","away"):
            x=lineup_position(pk,pid,side)
            if x:pos.append(x); break
    if not pos:return None
    c=Counter(pos); best=c.most_common(1)[0][1]; tied=[p for p,n in c.items() if n==best]
    return {"position":int(clamp(tied[0] if len(tied)==1 else round(sum(pos)/len(pos)),1,9)),"sample_games":len(pos)}

@st.cache_data(ttl=1800)
def statcast_tables():
    y=season(); urls=[f"{SAVANT}/leaderboard/expected_statistics?type=batter&year={y}&position=&team=&filterType=pa&min=1&csv=true",f"{SAVANT}/leaderboard/statcast?type=batter&year={y}&position=&team=&min=1&csv=true"]
    rs=[requests.get(u,headers=HEADERS,timeout=25) for u in urls]
    for r in rs:r.raise_for_status()
    return pd.read_csv(StringIO(rs[0].text)),pd.read_csv(StringIO(rs[1].text))

def statcast(pid):
    try:e,c=statcast_tables()
    except:return None
    ei,ci=col(e,["player_id","id"]),col(c,["player_id","id"])
    if ei is None or ci is None:return None
    er=e[pd.to_numeric(e[ei],errors="coerce")==int(pid)]; cr=c[pd.to_numeric(c[ci],errors="coerce")==int(pid)]
    if er.empty and cr.empty:return None
    a=er.iloc[0] if not er.empty else pd.Series(dtype=object); b=cr.iloc[0] if not cr.empty else pd.Series(dtype=object)
    return {"source":"Baseball Savant / Statcast","year":season(),
        "xba":sf(rowval(a,e,["est_ba","xba"])) if not er.empty else None,"xslg":sf(rowval(a,e,["est_slg","xslg"])) if not er.empty else None,
        "xwoba":sf(rowval(a,e,["est_woba","xwoba"])) if not er.empty else None,"pa":sf(rowval(a,e,["pa","plate_appearances"],0),0) if not er.empty else 0,
        "bbe":sf(rowval(b,c,["batted_ball","bbe"],0),0) if not cr.empty else 0,"avg_ev":sf(rowval(b,c,["exit_velocity_avg","avg_exit_velocity"])) if not cr.empty else None,
        "launch_angle":sf(rowval(b,c,["launch_angle_avg","avg_launch_angle"])) if not cr.empty else None,
        "hard_hit_rate":pct(rowval(b,c,["hard_hit_percent","hard_hit_pct"])) if not cr.empty else None,"barrel_rate":pct(rowval(b,c,["barrel_batted_rate","barrel_percent","brl_percent"])) if not cr.empty else None}

@st.cache_data(ttl=900)
def bullpen(team_id,starter_id=None):
    if not team_id:return None
    r=requests.get(f"{MLB_API}/teams/{int(team_id)}/roster",params={"rosterType":"active"},timeout=15); r.raise_for_status()
    ids=[int(e["person"]["id"]) for e in r.json().get("roster",[]) if e.get("position",{}).get("abbreviation")=="P" and e.get("person",{}).get("id")]
    rel=[]
    for pid in ids[:16]:
        if starter_id and pid==int(starter_id):continue
        try:p=pitcher_stats(pid)
        except:continue
        if not p or p["true_innings"]<=0:continue
        if p["games_started"]<=3 or p["games_started"]/max(p["games"],1)<=.35:rel.append(p)
    if not rel:return None
    ip=sum(p["true_innings"] for p in rel)
    if ip<=0:return None
    er=sum(p["earned_runs"] for p in rel); h=sum(p["hits_allowed"] for p in rel); bb=sum(p["walks"] for p in rel); k=sum(p["strikeouts"] for p in rel)
    rip=sum(p["true_innings"] for p in rel if str(p.get("hand")).upper()=="R"); lip=sum(p["true_innings"] for p in rel if str(p.get("hand")).upper()=="L"); hip=rip+lip; rs=rip/hip if hip else .6
    return {"reliever_count":len(rel),"innings":ip,"era":er*9/ip,"whip":(h+bb)/ip,"k9":k*9/ip,"right_share":clamp(rs,0,1),"left_share":clamp(1-rs,0,1)}

def matchup(df,team_id):
    if df.empty or team_id is None:return None
    for _,g in df.iterrows():
        if g.away_team_id==team_id:return {"game_pk":g.game_pk,"team_side":"away","venue_name":g.venue_name,"opponent_team_id":g.home_team_id,"opponent":g.home_team,"location":"Away","pitcher_id":g.home_pitcher_id,"pitcher":g.home_pitcher,"first_pitch":g.first_pitch_et,"status":g.status}
        if g.home_team_id==team_id:return {"game_pk":g.game_pk,"team_side":"home","venue_name":g.venue_name,"opponent_team_id":g.away_team_id,"opponent":g.away_team,"location":"Home","pitcher_id":g.away_pitcher_id,"pitcher":g.away_pitcher,"first_pitch":g.first_pitch_et,"status":g.status}

def hand_avg(base,sp):
    if not sp:return base,0
    a=sf(sp.get("avg")); n=sf(sp.get("at_bats"),0) or 0
    if a is None or n<=0:return base,0
    w=n/(n+200); return base*(1-w)+a*w,w
def quality(p,bp=False):
    if not p:return None
    era,whip,k9=sf(p.get("era")),sf(p.get("whip")),sf(p.get("k9")); inn=sf(p.get("innings" if bp else "true_innings"),0) or 0
    if era is None or whip is None:return None
    raw=.4*((4.2-era)/4.2)+.4*((1.3-whip)/1.3)+.2*(((k9-8.5)/8.5) if k9 is not None else 0); rel=inn/(inn+(120 if bp else 60)) if inn else 0; q=raw*rel
    adj=clamp((-.18 if bp else -.25)*q,-.05 if bp else -.08,.05 if bp else .08)
    grade="Very Tough" if q>=.1 else "Tough" if q>=.04 else "Very Favorable" if q<=-.1 else "Favorable" if q<=-.04 else "Near Neutral"
    return {"reliability":rel,"rate_adjustment":adj,"difficulty":grade}
def add_recent(base,r):
    if not r or r.get("avg") is None:return base,0,None
    n=r.get("at_bats",0) or 0; w=clamp(.22*(n/(n+45)),0,.22) if n else 0
    return base*(1-w)+r["avg"]*w,w,r["avg"]

PARK={"coors field":.035,"fenway park":.018,"kauffman stadium":.012,"chase field":.010,"great american ball park":.010,"citizens bank park":.008,"wrigley field":.006,"yankee stadium":.005,"daikin park":.004,"minute maid park":.004,"globe life field":.003,"camden yards":.002,"rogers centre":.002,"truist park":.002,"target field":.001,"loandepot park":-.003,"dodger stadium":-.004,"american family field":-.004,"citi field":-.006,"angel stadium":-.006,"nationals park":-.006,"rate field":-.007,"sutter health park":-.007,"petco park":-.010,"t-mobile park":-.016,"oracle park":-.018}
def env_adj(e,venue="Unknown"):
    e=e or {}; v=e.get("venue_name") or venue or "Unknown"; park=PARK.get(v.lower().strip(),0); t=e.get("temperature"); cond=str(e.get("condition") or "Unknown"); wind=str(e.get("wind") or "Unknown"); roof=str(e.get("roof_type") or "Unknown"); indoor=any(x in cond.lower() for x in ["dome","indoor","roof closed","closed roof"])
    ta=clamp(((t-72)/10)*.004,-.015,.015) if t is not None and not indoor else 0; wa=0; m=re.search(r"(\d+(?:\.\d+)?)\s*mph",wind,re.I); speed=sf(m.group(1)) if m else None
    if speed is not None and not indoor:
        sc=clamp(speed/15,0,1.5); low=wind.lower()
        if "out to" in low or "blowing out" in low:wa=clamp(.012*sc,0,.018)
        elif "in from" in low or "blowing in" in low:wa=clamp(-.012*sc,-.018,0)
    total=clamp(park+ta+wa,-.05,.05); grade="Strong Hitter Boost" if total>=.025 else "Hitter Friendly" if total>=.008 else "Strong Pitcher Boost" if total<=-.025 else "Pitcher Friendly" if total<=-.008 else "Near Neutral"
    return {"venue_name":v,"temperature":t,"condition":cond,"wind":wind,"roof_type":roof,"park_adjustment":park,"temperature_adjustment":ta,"wind_adjustment":wa,"total_adjustment":total,"grade":grade}
def add_statcast(base,s):
    if not s:return base,{"available":False,"reliability":0,"quality_adjustment":0,"grade":"Unavailable"}
    x=s.get("xba"); sample=max(sf(s.get("bbe"),0) or 0,(sf(s.get("pa"),0) or 0)*.65); rel=sample/(sample+120) if sample else 0; w=clamp(.22*rel,0,.22) if x is not None and .05<=x<=.5 else 0; blend=base*(1-w)+(x if x is not None else base)*w
    comps=[]; ev=s.get("avg_ev"); hh=s.get("hard_hit_rate"); br=s.get("barrel_rate")
    if ev is not None:comps.append(.35*clamp((ev-88.5)/7,-1.5,1.5))
    if hh is not None:comps.append(.35*clamp((hh-.4)/.2,-1.5,1.5))
    if br is not None:comps.append(.3*clamp((br-.08)/.09,-1.5,1.5))
    adj=clamp(.025*(sum(comps) if comps else 0)*rel,-.04,.04); final=clamp(blend*(1+adj),.05,.5); grade="Elite Contact" if adj>=.02 else "Strong Contact" if adj>=.007 else "Weak Contact" if adj<=-.02 else "Below-Average Contact" if adj<=-.007 else "Near Neutral"
    return final,{"available":True,"reliability":rel,"quality_adjustment":adj,"grade":grade}
def bullpen_rate(base,sr,sl,bp,recent,e,sc,venue):
    if not bp:return None
    ra,_=hand_avg(base,sr); la,_=hand_avg(base,sl); h=ra*bp.get("right_share",.6)+la*bp.get("left_share",.4); q=quality(bp,True); adj=q["rate_adjustment"] if q else 0; x=clamp(h*(1+adj),.05,.5); x,_,_=add_recent(x,recent); en=env_adj(e,venue); x=clamp(x*(1+en["total_adjustment"]),.05,.5); x,sm=add_statcast(x,sc)
    return {"rate":x,"quality":q,"quality_adjustment":adj,"statcast":sm}
def starter_exposure(p,ab):
    ip=(p.get("true_innings",0)/(p.get("games_started",0) or 1)) if p and p.get("games_started") else 5; ip=clamp(ip,4,6.5); sh=clamp(ip/9,.44,.72)
    return {"starter_ip":ip,"starter_share":sh,"starter_ab":ab*sh,"bullpen_ab":ab*(1-sh)}
def model_inputs(base,spot,m,p,sr,sl,recent,e,sc,bp):
    h=p.get("hand") if p else None; sp=sr if h=="R" else sl if h=="L" else None; ha,sw=hand_avg(base,sp); pq=quality(p); pa=clamp(ha*(1+(pq["rate_adjustment"] if pq else 0)),.05,.5); rr,rw,rav=add_recent(pa,recent); en=env_adj(e,(m or {}).get("venue_name","Unknown")); v8=clamp(rr*(1+en["total_adjustment"]),.05,.5); start,sm=add_statcast(v8,sc); bm=bullpen_rate(base,sr,sl,bp,recent,e,sc,(m or {}).get("venue_name","Unknown")); br=bm["rate"] if bm else start; ex=starter_exposure(p,ab_for_spot(spot)); bq=bm["quality"] if bm else None
    return {"starter_split":sp,"hand_avg":ha,"split_weight":sw,"pitcher_quality":pq,"pitcher_avg":pa,"recent_model":rr,"recent_weight":rw,"recent_avg":rav,"env_model":en,"v8_avg":v8,"starter_rate":start,"statcast_model":sm,"bullpen_model":bm,"bullpen_quality":bq,"bullpen_rate":br,"expected_ab":ab_for_spot(spot),"exposure":ex}

def sim_seed(pid,pk,salt=0): return int((int(pid)*1009+int(pk or 0)*17+int(datetime.now(ET).strftime("%Y%m%d"))+salt)%(2**32-1))
@st.cache_data(ttl=600,show_spinner=False)
def monte(starter,bullpen,ab,share,split_w,sc_rel,p_rel,b_rel,n,seed):
    n=int(n); bs=250000; rng=np.random.default_rng(int(seed)); cs=max(130+220*split_w+180*sc_rel+140*p_rel,60); cb=max(100+150*sc_rel+180*b_rel,50); sa=max(starter*cs,.5); sb=max((1-starter)*cs,.5); ba=max(bullpen*cb,.5); bb=max((1-bullpen)*cb,.5); hist=np.zeros(8,dtype=np.int64); probs=[]; samples=[]; hit_sum=done=batches=0
    while done<n:
        k=min(bs,n-done); abs_=np.clip(np.rint(rng.normal(ab,.55,k)).astype(np.int8),2,7); sh=np.clip(rng.normal(share,.075,k),.25,.9); sab=rng.binomial(abs_.astype(np.int16),sh); bab=abs_.astype(np.int16)-sab; sr=rng.beta(sa,sb,k); br=rng.beta(ba,bb,k); hits=rng.binomial(sab,sr)+rng.binomial(bab,br); hist+=np.bincount(np.minimum(hits,7),minlength=8)[:8]; hit_sum+=float(hits.sum()); probs.append(float(np.mean(hits>=1))); sp=1-np.power(1-sr,sab)*np.power(1-br,bab); take=min(10000,k); samples.append(sp[rng.choice(k,size=take,replace=False)].astype(np.float32)); done+=k; batches+=1
    p0=hist[0]/done; p1=1-p0; ss=np.concatenate(samples); lo,hi=[float(x) for x in np.percentile(ss,[5,95])]; spread=max(probs)-min(probs) if probs else 0; cdf=np.cumsum(hist)/done
    return {"simulations":done,"batches":batches,"seed":int(seed),"p_zero":float(p0),"p_one_plus":float(p1),"p_exact_one":float(hist[1]/done),"p_two_plus":float(hist[2:].sum()/done),"p_three_plus":float(hist[3:].sum()/done),"expected_hits":float(hit_sum/done),"median_hits":int(np.searchsorted(cdf,.5)),"mode_hits":int(np.argmax(hist)),"mc_se":float(np.sqrt(p1*(1-p1)/done)),"scenario_low":lo,"scenario_high":hi,"batch_range":float(spread),"converged":bool(spread<=.005)}
def confidence(stats,p,sp,recent,confirmed,e,sc,bp,sim):
    score=sum(map(bool,[stats,p,sp,recent,confirmed,e,sc,bp])); width=sim["scenario_high"]-sim["scenario_low"]
    grade="HIGH" if score>=7 and width<=.18 and sim["converged"] else "MEDIUM-HIGH" if score>=5 and width<=.25 and sim["converged"] else "MEDIUM" if score>=4 else "LOW"
    return grade,score

def slate_candidates(df,include_live=False):
    out=[]; checked=with_lineups=0
    for _,g in df.iterrows():
        if not actionable(g.status,include_live):continue
        checked+=1
        try:s=lineup_snapshot(int(g.game_pk))
        except:continue
        if not s.get("away") and not s.get("home"):continue
        with_lineups+=1
        for side in ("away","home"):
            team=g.away_team if side=="away" else g.home_team; tid=g.away_team_id if side=="away" else g.home_team_id; opp=g.home_team if side=="away" else g.away_team; oid=g.home_team_id if side=="away" else g.away_team_id; sid=g.home_pitcher_id if side=="away" else g.away_pitcher_id; sname=g.home_pitcher if side=="away" else g.away_pitcher
            for h in s.get(side,[]):
                avg=sf(h.get("avg"))
                if avg is None:
                    try:avg=sf((hitter_stats(h["player_id"]) or {}).get("avg"))
                    except:avg=None
                if avg is None or avg<=0:continue
                out.append({**h,"season_avg":avg,"team":team,"team_id":tid,"opponent":opp,"opponent_team_id":oid,"starter_id":sid,"starter_name":sname,"game_pk":int(g.game_pk),"venue_name":g.venue_name,"status":g.status,"first_pitch":g.first_pitch_et,"team_side":side})
    return out,checked,with_lineups
def prescreen(c):
    p=None; sp=None
    if c.get("starter_id") and pd.notna(c.get("starter_id")):
        try:p=pitcher_stats(int(c["starter_id"]))
        except:pass
    if p:
        try:sp=hand_split(c["player_id"],p.get("hand"))
        except:pass
    ha,_=hand_avg(c["season_avg"],sp); q=quality(p); rate=clamp(ha*(1+(q["rate_adjustment"] if q else 0)),.05,.5)
    try:e=environment(c["game_pk"])
    except:e=None
    en=env_adj(e,c["venue_name"]); rate=clamp(rate*(1+en["total_adjustment"]),.05,.5); pr=p_from_avg(rate,ab_for_spot(c["position"]))
    return {**c,"screen_rate":rate,"screen_p1":pr["p_one_plus"],"pitcher":p,"starter_split":sp,"environment":e}
def deep_scan(c,n):
    base=c["season_avg"]; p=c.get("pitcher"); e=c.get("environment")
    try:sr=hand_split(c["player_id"],"R")
    except:sr=None
    try:sl=hand_split(c["player_id"],"L")
    except:sl=None
    try:r=recent_form(c["player_id"],10)
    except:r=None
    sc=statcast(c["player_id"])
    try:bp=bullpen(c["opponent_team_id"],c.get("starter_id"))
    except:bp=None
    m={"game_pk":c["game_pk"],"venue_name":c["venue_name"],"opponent":c["opponent"],"opponent_team_id":c["opponent_team_id"],"pitcher_id":c.get("starter_id"),"pitcher":c.get("starter_name"),"status":c["status"]}
    z=model_inputs(base,c["position"],m,p,sr,sl,r,e,sc,bp); seed=sim_seed(c["player_id"],c["game_pk"],1200); sim=monte(z["starter_rate"],z["bullpen_rate"],z["expected_ab"],z["exposure"]["starter_share"],z["split_weight"],z["statcast_model"].get("reliability",0),z["pitcher_quality"].get("reliability",0) if z["pitcher_quality"] else 0,z["bullpen_quality"].get("reliability",0) if z["bullpen_quality"] else 0,n,seed); grade,score=confidence({"avg":base},p,z["starter_split"],r,True,e,sc,bp,sim)
    return {**c,"sim":sim,"confidence":grade,"data_score":score,"starter_rate":z["starter_rate"],"bullpen_rate":z["bullpen_rate"],"expected_ab":z["expected_ab"]}
def load_player(name,df):
    p=player_search(name)
    if not p:return None
    stats=hitter_stats(p["id"]); r=recent_form(p["id"],10); m=matchup(df,p["team_id"]); pitch=e=bp=None; confirmed=est=None
    if m:
        confirmed=lineup_position(m["game_pk"],p["id"],m["team_side"]); e=environment(m["game_pk"])
        if pd.notna(m.get("pitcher_id")):pitch=pitcher_stats(int(m["pitcher_id"]))
    if r:est=recent_lineup_position(p["id"],r.get("game_pks",[]),5)
    sr=hand_split(p["id"],"R"); sl=hand_split(p["id"],"L"); sc=statcast(p["id"])
    if m:
        try:bp=bullpen(m["opponent_team_id"],m.get("pitcher_id"))
        except:pass
    return {"player":p,"stats":stats,"recent":r,"matchup":m,"pitcher":pitch,"split_r":sr,"split_l":sl,"confirmed_lineup":confirmed,"recent_lineup":est,"environment":e,"statcast":sc,"bullpen":bp}
