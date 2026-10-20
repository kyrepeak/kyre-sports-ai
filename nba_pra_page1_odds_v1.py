"""NBA PRA source adapter."""
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
from nba_pra_page1_sgo_v1 import _list_payload
def _walk(value: Any):
    if isinstance(value,Mapping):
        yield value
        for child in value.values(): yield from _walk(child)
    elif isinstance(value,list):
        for child in value: yield from _walk(child)

def normalize_odds_api_pra(payload: Any)->list[dict[str,Any]]:
    rows=[]
    bookmakers=payload.get("bookmakers") if isinstance(payload,Mapping) else None
    if isinstance(bookmakers,Mapping):
        for book,markets in bookmakers.items():
            for market in markets if isinstance(markets,list) else []:
                if not isinstance(market,Mapping) or _text(market.get("name")).casefold()!="player props": continue
                observed=_text(market.get("updatedAt") or market.get("lastUpdated"))
                for odd in market.get("odds",[]) if isinstance(market.get("odds"),list) else []:
                    if not isinstance(odd,Mapping): continue
                    label=_text(odd.get("label")); ln=_norm(label)
                    if "pointsreboundsassists" not in ln and not ln.endswith("pra"): continue
                    marker=None
                    lower=label.casefold()
                    for text in ("points + rebounds + assists","points rebounds assists","pra"):
                        idx=lower.find(text)
                        if idx>=0: marker=idx; break
                    player=label[:marker].rstrip(" -:|") if marker is not None else ""
                    line=_num(odd.get("hdp") if odd.get("hdp") is not None else odd.get("line"))
                    if not player or line is None: continue
                    for side in ("over","under"):
                        if odd.get(side) is None: continue
                        rows.append({"provider":"Odds-API.io","player_name":player,"sportsbook":_text(book),"side":side,"line":line,"price":_decimal_to_american(odd.get(side)),"observed_at_utc":observed})
    for node in _walk(payload):
        market=_text(node.get("market") or node.get("marketName") or node.get("key")); mn=_norm(market)
        if "pointsreboundsassists" not in mn and not mn.endswith("pra"): continue
        player=_text(node.get("player") or node.get("playerName") or node.get("participant") or node.get("description")); book=_text(node.get("bookmaker") or node.get("bookmakerName") or node.get("sportsbook")); outcomes=node.get("outcomes")
        if not isinstance(outcomes,list): continue
        for out in outcomes:
            if not isinstance(out,Mapping): continue
            side=_text(out.get("name") or out.get("side")).casefold(); line=_num(out.get("point") if out.get("point") is not None else out.get("line"))
            if side not in {"over","under"} or line is None: continue
            rows.append({"provider":"Odds-API.io","player_name":player or _text(out.get("description")),"sportsbook":book,"side":side,"line":line,"price":_american(out.get("price") or out.get("odds")),"observed_at_utc":_text(node.get("updatedAt") or node.get("lastUpdated"))})
    dedup=[]; seen=set()
    for row in rows:
        if not row.get("player_name"): continue
        key=(_norm(row.get("player_name")),row.get("sportsbook"),row.get("side"),row.get("line"),row.get("price"))
        if key in seen: continue
        seen.add(key); dedup.append(row)
    return dedup

def load_odds_api_pra_observations(slate_date: date, *, request_get: Callable[...,Any]=_default_get, secret_getter: Callable[[str],str|None]=_default_secret, timeout: float=6.0)->dict[str,Any]:
    base={"source":"Odds-API.io","observations":[],"fabrication":False,"sportsbook_projection_influence":0.0}
    key=_text(secret_getter("ODDS_API_IO_KEY") or secret_getter("ODDS_API_KEY"))
    if not key: return {**base,"verification":"UNAVAILABLE","diagnostic_state":"ODDS_API_IO_CREDENTIAL_UNAVAILABLE"}
    try:
        ev=request_get(f"{ODDS_API_BASE}/events",params={"apiKey":key,"sport":"nba","status":"pending","limit":100},timeout=timeout); ev.raise_for_status(); ids=[_text(x.get("id")) for x in _list_payload(ev.json()) if x.get("id")]
        rows=[]
        for event_id in ids:
            res=request_get(f"{ODDS_API_BASE}/odds",params={"apiKey":key,"eventId":event_id,"bookmakers":ODDS_API_BOOKMAKERS,"markets":"Player Props"},timeout=timeout); res.raise_for_status(); rows.extend(normalize_odds_api_pra(res.json()))
    except Exception as exc: return {**base,"verification":"UNAVAILABLE","diagnostic_state":f"ODDS_API_IO_ERROR:{type(exc).__name__}"}
    return {**base,"verification":"VERIFIED" if rows else "UNAVAILABLE","diagnostic_state":"OK" if rows else "ODDS_API_IO_NO_PRA","observations":rows}

def reconcile_pra_market(*payloads: Mapping[str,Any])->dict[str,dict[str,Any]]:
    rows=[dict(r) for p in payloads for r in (p.get("observations") or []) if isinstance(r,Mapping) and _text(r.get("player_name")) and _num(r.get("line")) is not None]
    grouped={}
    for r in rows: grouped.setdefault(_norm(r["player_name"]),[]).append(r)
    result={}
    for key,values in grouped.items():
        books=sorted({_text(v.get("sportsbook")) for v in values if _text(v.get("sportsbook"))}); providers=sorted({_text(v.get("provider")) for v in values if _text(v.get("provider"))}); consensus=median([float(v["line"]) for v in values]); selected=min(values,key=lambda v:abs(float(v["line"])-consensus)); line=float(selected["line"])
        over=[v for v in values if v.get("side")=="over" and float(v["line"])==line]; under=[v for v in values if v.get("side")=="under" and float(v["line"])==line]
        result[key]={"player_name":selected["player_name"],"line":line,"over_price":max([v["price"] for v in over if v.get("price") is not None],default=None),"under_price":max([v["price"] for v in under if v.get("price") is not None],default=None),"book_count":len(books),"books":books,"providers":providers,"observed_at_utc":max([_text(v.get("observed_at_utc")) for v in values],default=""),"away_team":_text(selected.get("away_team")),"home_team":_text(selected.get("home_team"))}
    return result

