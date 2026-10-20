"""NBA PRA Page 1 multi-source read-only data layer.

Uses verified NBA Official + ESPN + CBS schedule ownership already in the repo,
NBA Official + ESPN injury context, SportsGameOdds and Odds-API.io PRA markets,
and ESPN NBA roster/gamelog data. All source failures fail closed.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from functools import lru_cache
import os, re
from zoneinfo import ZoneInfo
from statistics import median
from typing import Any, Callable, Mapping, Sequence

MODEL_VERSION="NBA PRA PAGE1 DATA V1"
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
SGO_BASE="https://api.sportsgameodds.com/v2"; SGO_LEAGUE_ID="NBA"
ODDS_API_BASE="https://api.odds-api.io/v3"
SGO_BOOKMAKERS="draftkings,fanduel,betmgm,caesars"
ODDS_API_BOOKMAKERS="DraftKings,FanDuel,BetMGM,Caesars,Pinnacle,ESPN BET,Fanatics,Bet365"
PRA_STAT_IDS={"points_rebounds_assists","points+rebounds+assists","pra"}
BOOK_LABELS={"draftkings":"DraftKings","fanduel":"FanDuel","betmgm":"BetMGM","caesars":"Caesars"}
ESPN_ROSTER_BASE="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_GAMELOG_BASE="https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes"


from nba_pra_page1_common_v1 import _text, _norm, _num, nba_season_end_year
def normalize_espn_roster(payload: Mapping[str,Any])->list[dict[str,Any]]:
    raw=payload.get("athletes") or []; athletes=[]
    for item in raw if isinstance(raw,list) else []:
        if not isinstance(item,Mapping): continue
        members=item.get("items")
        athletes.extend(members if isinstance(members,list) else [item])
    rows=[]
    for a in athletes:
        if not isinstance(a,Mapping): continue
        pos=a.get("position") or {}; head=a.get("headshot") or {}
        rows.append({"id":_text(a.get("id")),"name":_text(a.get("displayName") or a.get("fullName")),"position":_text(pos.get("abbreviation") if isinstance(pos,Mapping) else pos),"headshot":_text(head.get("href") if isinstance(head,Mapping) else head)})
    return [r for r in rows if r["id"] and r["name"]]

def _regular_season(st: Mapping[str,Any])->bool:
    value=st.get("type") or st.get("id"); name=_text(st.get("name") or st.get("displayName")).casefold()
    return value in (None,"",2,"2") or "regular" in name

def normalize_espn_gamelog(payload: Mapping[str,Any])->list[dict[str,Any]]:
    rows=[]
    for st in payload.get("seasonTypes",[]) or []:
        if not isinstance(st,Mapping) or not _regular_season(st): continue
        for category in st.get("categories",[]) or []:
            if not isinstance(category,Mapping): continue
            axis=category.get("names") or category.get("labels") or []
            for event in category.get("events",[]) or []:
                if not isinstance(event,Mapping): continue
                stats=event.get("stats") or event.get("statistics") or []
                if not isinstance(axis,list) or not isinstance(stats,list) or len(axis)!=len(stats): continue
                mapped={_norm(k):v for k,v in zip(axis,stats)}
                def pick(*keys):
                    for k in keys:
                        if _norm(k) in mapped: return _num(mapped[_norm(k)])
                    return None
                pts,reb,ast=pick("PTS","points"),pick("REB","rebounds","totalRebounds"),pick("AST","assists")
                if None in (pts,reb,ast): continue
                rows.append({"event_id":_text(event.get("eventId") or event.get("id")),"date":_text(event.get("date")),"minutes":pick("MIN","minutes"),"points":pts,"rebounds":reb,"assists":ast})
    return rows

@lru_cache(maxsize=64)
def load_espn_roster(team_code: str)->tuple[dict[str,Any],...]:
    try:
        response=_default_get(f"{ESPN_ROSTER_BASE}/{_text(team_code).lower()}/roster",timeout=4.0); response.raise_for_status(); return tuple(normalize_espn_roster(response.json()))
    except Exception: return ()
@lru_cache(maxsize=256)
def load_espn_gamelog(player_id: str, season: int)->tuple[dict[str,Any],...]:
    try:
        response=_default_get(f"{ESPN_GAMELOG_BASE}/{int(player_id)}/gamelog",params={"season":int(season)},timeout=4.0); response.raise_for_status(); return tuple(normalize_espn_gamelog(response.json()))
    except Exception: return ()

def build_player_profiles(games: Sequence[Mapping[str,Any]], market: Mapping[str,Mapping[str,Any]], slate_date: date)->dict[str,dict[str,Any]]:
    teams=sorted({_text(g.get(k)).upper() for g in games for k in ("away_tricode","home_tricode") if _text(g.get(k))})
    roster=[dict(row,team=team) for team in teams for row in load_espn_roster(team)]; by_name={_norm(r["name"]):r for r in roster}
    profiles={key:{"player_name":q.get("player_name"),"espn_id":"","team":"","position":"","headshot":"","current_games":[],"prior_games":[]} for key,q in market.items()}
    for key,p in profiles.items():
        r=by_name.get(key)
        if r: p.update({"player_name":r["name"],"espn_id":r["id"],"team":r["team"],"position":r["position"],"headshot":r["headshot"]})
    season=nba_season_end_year(slate_date); jobs={}
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(profiles)*2))) as pool:
        for key,p in profiles.items():
            if not p["espn_id"]: continue
            jobs[pool.submit(load_espn_gamelog,p["espn_id"],season)]=(key,"current_games"); jobs[pool.submit(load_espn_gamelog,p["espn_id"],season-1)]=(key,"prior_games")
        for future in as_completed(jobs):
            key,field=jobs[future]
            try: profiles[key][field]=list(future.result())
            except Exception: profiles[key][field]=[]
    return profiles

