"""NBA Spread Step 6 — fail-closed sportsbook spread market context.

This layer is market context only. It never changes projections, probabilities,
injury logic, ranking, or later decision layers. A verified context requires an
exact frozen Step-3 upcoming/delayed matchup plus at least two independent
sportsbook quotes for the same semantic SPORTSBOOK_LINES metric.
"""
from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from devsystem.universal_sports_field_router_v1 import load_router_policy, route_field
from devsystem.universal_sports_provider_registry_v1 import load_registry
from nba_spread_sportsbook_observations_v1 import load_verified_sportsbook_observations

MODEL_VERSION = "NBA_SPREAD_STEP6_MARKET_LINES_V1"
MARKET_SECTION_LABEL = "Market Spread"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_ACTIVATE_MARKET_LINES = True
MAY_ACTIVATE_INJURIES = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_RANKING = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}

_ROOT = Path(__file__).resolve().parent
_PROVIDER_REGISTRY_PATH = _ROOT / "devsystem" / "contracts" / "universal-sports-provider-registry-v1.json"
_FIELD_ROUTER_PATH = _ROOT / "devsystem" / "contracts" / "universal-sports-field-router-v1.json"


def _tricode(value: object) -> str | None:
    text = str(value or "").strip().upper()
    return text if len(text) == 3 and text.isalpha() else None


def _spread(value: object) -> float | None:
    if isinstance(value, bool): return None
    try: parsed = float(value)
    except (TypeError, ValueError): return None
    return parsed if math.isfinite(parsed) else None


def _schedule_index(schedule_games: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], Mapping[str, object]]:
    out = {}
    for game in schedule_games:
        if str(game.get("status") or "").strip().upper() not in ELIGIBLE_STATES: continue
        away, home = _tricode(game.get("away_tricode")), _tricode(game.get("home_tricode"))
        if away and home: out[(away, home)] = game
    return out


def build_spread_market_context(rows: Iterable[Mapping[str, object]], schedule_games: Sequence[Mapping[str, object]]) -> dict:
    schedule = _schedule_index(schedule_games); grouped = {}
    for row in rows:
        away, home = _tricode(row.get("away_tricode")), _tricode(row.get("home_tricode"))
        if away and home and (away, home) in schedule: grouped.setdefault((away, home), []).append(row)
    if not grouped: return {"verification":"UNAVAILABLE","diagnostic_state":"NO_VERIFIED_SCHEDULE_MATCH"}
    if len(grouped) != 1: return {"verification":"UNAVAILABLE","diagnostic_state":"AMBIGUOUS_MARKET_GAME"}
    key, matched = next(iter(grouped.items())); books=set(); verified=[]
    for row in matched:
        sportsbook=str(row.get("sportsbook") or "").strip()
        if not sportsbook: return {"verification":"UNAVAILABLE","diagnostic_state":"SPORTSBOOK_ID_UNVERIFIED"}
        book_key=sportsbook.casefold()
        if book_key in books: return {"verification":"UNAVAILABLE","diagnostic_state":"DUPLICATE_SPORTSBOOK_QUOTE"}
        books.add(book_key); away_spread=_spread(row.get("away_spread")); home_spread=_spread(row.get("home_spread"))
        if away_spread is None or home_spread is None or not math.isclose(away_spread+home_spread,0.0,abs_tol=1e-9): return {"verification":"UNAVAILABLE","diagnostic_state":"INVALID_SPREAD_PAIR"}
        verified.append((sportsbook,away_spread,home_spread))
    if len(verified)<2: return {"verification":"UNAVAILABLE","diagnostic_state":"CONSENSUS_QUORUM_NOT_MET"}
    away,home=key; game=schedule[key]; best_away=max(verified,key=lambda r:r[1]); best_home=max(verified,key=lambda r:r[2])
    return {"verification":"VERIFIED","away_tricode":away,"home_tricode":home,"away_name":str(game.get("away_name") or away),"home_name":str(game.get("home_name") or home),"game_date_phoenix":str(game.get("game_date_phoenix") or ""),"tip_phoenix":str(game.get("tip_phoenix") or ""),"status":str(game.get("status") or "UPCOMING"),"sportsbook_count":len(verified),"consensus_away_spread":float(median([r[1] for r in verified])),"consensus_home_spread":float(median([r[2] for r in verified])),"best_away":{"sportsbook":best_away[0],"spread":best_away[1]},"best_home":{"sportsbook":best_home[0],"spread":best_home[2]},"fabrication":False,"page_wide_source_authority":False}


def resolve_spread_market_route(*, registry: Mapping[str, Any] | None=None, router_policy: Mapping[str, Any] | None=None) -> dict[str, Any]:
    resolved_registry=dict(registry) if registry is not None else load_registry(_PROVIDER_REGISTRY_PATH)
    resolved_policy=dict(router_policy) if router_policy is not None else load_router_policy(_FIELD_ROUTER_PATH)
    return route_field(resolved_registry,resolved_policy,sport="nba",field="sportsbook_lines")


def load_spread_market_features(schedule_games: Sequence[Mapping[str, object]]) -> dict:
    try: route=resolve_spread_market_route()
    except (OSError,TypeError,ValueError): return {"verification":"UNAVAILABLE","diagnostic_state":"SPORTSBOOK_ROUTE_UNAVAILABLE","semantic_metric_id":"SPORTSBOOK_LINES","fabrication":False,"page_wide_source_authority":False}
    if route.get("status") != "ROUTE_READY": return {"verification":"UNAVAILABLE","diagnostic_state":"SPORTSBOOK_ROUTE_UNAVAILABLE","semantic_metric_id":"SPORTSBOOK_LINES","route_id":route.get("route_id"),"eligible_provider_ids":list(route.get("eligible_provider_ids") or []),"blocked_providers":list(route.get("blocked_providers") or []),"active_provider_ids":list(route.get("active_provider_ids") or []),"fabrication":False,"page_wide_source_authority":False}
    transport=load_verified_sportsbook_observations(schedule_games)
    if transport.get("verification") != "VERIFIED": return {**transport,"semantic_metric_id":"SPORTSBOOK_LINES","route_id":route.get("route_id"),"eligible_provider_ids":list(route.get("eligible_provider_ids") or []),"blocked_providers":list(route.get("blocked_providers") or []),"active_provider_ids":list(route.get("active_provider_ids") or [])}
    result=build_spread_market_context(transport.get("observations") or [],schedule_games)
    result.update({"semantic_metric_id":"SPORTSBOOK_LINES","route_id":route.get("route_id"),"active_provider_ids":["direct_sportsbook_feed"]})
    return result


__all__=["MODEL_VERSION","MARKET_SECTION_LABEL","SPORTSBOOK_PROJECTION_INFLUENCE","MAY_ACTIVATE_MARKET_LINES","MAY_ACTIVATE_INJURIES","MAY_MODIFY_MODEL","MAY_MODIFY_PROJECTION","MAY_MODIFY_PROBABILITY","MAY_ACTIVATE_RANKING","build_spread_market_context","resolve_spread_market_route","load_spread_market_features"]
