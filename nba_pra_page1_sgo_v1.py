"""NBA PRA market adapter A."""
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


from nba_pra_page1_common_v1 import _text, _norm, _num, _american, _decimal_to_american, _default_secret, _default_get, nba_season_end_year, phoenix_date, select_next_active_slate
def build_sgo_odd_id_filter()->str:
    return ",".join(f"points+rebounds+assists-PLAYER_ID-game-ou-{side}" for side in ("over","under"))

def _event_name(event: Mapping[str,Any], side: str)->str:
    team=((event.get("teams") or {}).get(side) or {}) if isinstance(event.get("teams"),Mapping) else {}
    names=team.get("names") or {}
    if isinstance(names,Mapping):
        for key in ("long","display","medium","short"):
            if names.get(key): return _text(names[key])
    return _text(team.get("name") or team.get("teamName"))

def _player_name(event: Mapping[str,Any], player_id: str, market_name: Any)->str:
    players=event.get("players") or {}; player=players.get(player_id) if isinstance(players,Mapping) else None
    if isinstance(player,Mapping):
        names=player.get("names") or {}
        if isinstance(names,Mapping):
            for key in ("long","display","full","medium","short"):
                if names.get(key): return _text(names[key])
        for key in ("name","displayName","fullName"):
            if player.get(key): return _text(player[key])
    raw=_text(market_name); lowered=raw.casefold()
    for suffix in (" points + rebounds + assists"," points rebounds assists"," pra"):
        if suffix in lowered: return raw[:lowered.index(suffix)].strip()
    return ""

def parse_sgo_event_props(event: Mapping[str,Any])->list[dict[str,Any]]:
    odds=event.get("odds") or {}; rows=[]
    if not isinstance(odds,Mapping): return rows
    for odd_id,odd in odds.items():
        if not isinstance(odd,Mapping): continue
        stat=_text(odd.get("statID")).casefold(); side=_text(odd.get("sideID")).casefold(); pid=_text(odd.get("playerID") or odd.get("statEntityID"))
        if stat not in PRA_STAT_IDS or _text(odd.get("periodID")).casefold()!="game" or _text(odd.get("betTypeID")).casefold()!="ou" or side not in {"over","under"} or not pid: continue
        books=odd.get("byBookmaker") or {}
        if not isinstance(books,Mapping): continue
        for book,quote in books.items():
            if not isinstance(quote,Mapping) or quote.get("available") is False: continue
            line=_num(quote.get("overUnder"))
            if line is None: continue
            rows.append({"provider":"SportsGameOdds","provider_event_id":_text(event.get("eventID") or event.get("id")),"provider_player_id":pid,"player_name":_player_name(event,pid,odd.get("marketName")),"sportsbook":BOOK_LABELS.get(_norm(book),_text(book)),"side":side,"line":line,"price":_american(quote.get("odds")),"observed_at_utc":_text(quote.get("lastUpdatedAt") or event.get("updatedAt")),"away_team":_event_name(event,"away"),"home_team":_event_name(event,"home")})
    return [r for r in rows if r["player_name"]]

def _list_payload(payload: Any)->list[dict[str,Any]]:
    if isinstance(payload,list): return [dict(x) for x in payload if isinstance(x,Mapping)]
    if isinstance(payload,Mapping):
        for key in ("data","events","items"):
            value=payload.get(key)
            if isinstance(value,list): return [dict(x) for x in value if isinstance(x,Mapping)]
    return []

def load_sgo_pra_observations(slate_date: date, *, request_get: Callable[...,Any]=_default_get, secret_getter: Callable[[str],str|None]=_default_secret, timeout: float=6.0)->dict[str,Any]:
    base={"source":"SportsGameOdds","observations":[],"fabrication":False,"sportsbook_projection_influence":0.0}
    key=_text(secret_getter("SPORTSGAMEODDS_API_KEY") or secret_getter("SGO_API_KEY"))
    if not key: return {**base,"verification":"UNAVAILABLE","diagnostic_state":"SGO_CREDENTIAL_UNAVAILABLE"}
    try:
        response=request_get(f"{SGO_BASE}/events",headers={"X-API-Key":key},params={"leagueID":"NBA","startsAfter":f"{slate_date}T00:00:00Z","startsBefore":f"{slate_date}T23:59:59Z","oddsAvailable":"true","bookmakerID":SGO_BOOKMAKERS,"oddIDs":build_sgo_odd_id_filter(),"limit":100},timeout=timeout); response.raise_for_status()
        rows=[row for event in _list_payload(response.json()) for row in parse_sgo_event_props(event)]
    except Exception as exc: return {**base,"verification":"UNAVAILABLE","diagnostic_state":f"SGO_ERROR:{type(exc).__name__}"}
    return {**base,"verification":"VERIFIED" if rows else "UNAVAILABLE","diagnostic_state":"OK" if rows else "SGO_NO_PRA","observations":rows}

