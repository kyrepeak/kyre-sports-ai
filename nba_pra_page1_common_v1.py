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


def _text(v: Any)->str: return str(v or "").strip()
def _norm(v: Any)->str: return re.sub(r"[^a-z0-9]+","",_text(v).casefold())
def _num(v: Any)->float|None:
    if isinstance(v,bool): return None
    try: x=float(v)
    except (TypeError,ValueError): return None
    return x if x==x else None
def _american(v: Any)->int|None:
    try: return int(round(float(v)))
    except (TypeError,ValueError): return None

def _decimal_to_american(v: Any)->int|None:
    x=_num(v)
    if x is None: return None
    if abs(x)>=20: return int(round(x))
    if x<=1: return None
    return int(round((x-1)*100)) if x>=2 else int(round(-100/(x-1)))

def _default_secret(name: str)->str|None:
    value=os.getenv(name)
    if value: return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception: return None

def _default_get(*args,**kwargs):
    import requests
    return requests.get(*args,**kwargs)

def nba_season_end_year(day: date)->int: return day.year+1 if day.month>=7 else day.year

PHOENIX_TZ=ZoneInfo("America/Phoenix")
def phoenix_date(now: datetime)->date:
    if now.tzinfo is None: now=now.replace(tzinfo=timezone.utc)
    return now.astimezone(PHOENIX_TZ).date()

def select_next_active_slate(games: Sequence[Mapping[str,Any]], today: date)->tuple[str|None,list[dict[str,Any]]]:
    buckets: dict[str,list[dict[str,Any]]]={}
    for game in games:
        d=_text(game.get("game_date_phoenix"))[:10]
        if d: buckets.setdefault(d,[]).append(dict(game))
    eligible=sorted(d for d in buckets if d>=today.isoformat())
    if not eligible: return None,[]
    return eligible[0],buckets[eligible[0]]

