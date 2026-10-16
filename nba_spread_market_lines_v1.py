"""NBA Spread Step 6 — fail-closed sportsbook spread market context."""
from __future__ import annotations
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence
from devsystem.universal_sports_field_router_v1 import load_router_policy, route_field
from devsystem.universal_sports_provider_registry_v1 import load_registry
from nba_spread_sportsbook_observations_v1 import load_verified_sportsbook_observations
MODEL_VERSION="NBA_SPREAD_STEP6_MARKET_LINES_V1"; MARKET_SECTION_LABEL="Market Spread"; SPORTSBOOK_PROJECTION_INFLUENCE=0.0
MAY_ACTIVATE_MARKET_LINES=True; MAY_ACTIVATE_INJURIES=False; MAY_MODIFY_MODEL=False; MAY_MODIFY_PROJECTION=False; MAY_MODIFY_PROBABILITY=False; MAY_ACTIVATE_RANKING=False
ELIGIBLE_STATES={"UPCOMING","DELAYED"}; _ROOT=Path(__file__).resolve().parent; _PROVIDER_REGISTRY_PATH=_ROOT/"devsystem/contracts/universal-sports-provider-registry-v1.json"; _FIELD_ROUTER_PATH=_ROOT/"devsystem/contracts/universal-sports-field-router-v1.json"
def _tricode(v):
 t=str(v or "").strip().upper(); return t if len(t)==3 and t.isalpha() else None
def _spread(v):
 if isinstance(v,bool): return None
 try: p=float(v)
 except (TypeError,ValueError): return None
 return p if math.isfinite(p) else None
def _schedule_index(games):
 out={}
 for g in games:
  if str(g.get("status") or "").strip().upper() not in ELIGIBLE_STATES: continue
  a,h=_tricode(g.get("away_tricode")),_tricode(g.get("home_tricode"))
  if a and h: out[(a,h)]=g
 return out
def build_spread_market_context(rows:Iterable[Mapping[str,object]],schedule_games:Sequence[Mapping[str,object]])->dict:
 schedule=_schedule_index(schedule_games); grouped={}
 for r in rows:
  a,h=_tricode(r.get("away_tricode")),_tricode(r.get("home_tricode"))
  if a and h and (a,h) in schedule: grouped.setdefault((a,h),[]).append(r)
 if not grouped:return {"verification":"UNAVAILABLE","diagnostic_state":"NO_VERIFIED_SCHEDULE_MATCH"}
 if len(grouped)!=1:return {"verification":"UNAVAILABLE","diagnostic_state":"AMBIGUOUS_MARKET_GAME"}
 key,matched=next(iter(grouped.items())); books=set(); verified=[]
 for r in matched:
  book=str(r.get("sportsbook") or "").strip()
  if not book:return {"verification":"UNAVAILABLE","diagnostic_state":"SPORTSBOOK_ID_UNVERIFIED"}
  bk=book.casefold()
  if bk in books:return {"verification":"UNAVAILABLE","diagnostic_state":"DUPLICATE_SPORTSBOOK_QUOTE"}
  books.add(bk); a,h=_spread(r.get("away_spread")),_spread(r.get("home_spread"))
  if a is None or h is None or not math.isclose(a+h,0.0,abs_tol=1e-9):return {"verification":"UNAVAILABLE","diagnostic_state":"INVALID_SPREAD_PAIR"}
  verified.append((book,a,h))
 if len(verified)<2:return {"verification":"UNAVAILABLE","diagnostic_state":"CONSENSUS_QUORUM_NOT_MET"}
 a,h=key; g=schedule[key]; ba=max(verified,key=lambda x:x[1]); bh=max(verified,key=lambda x:x[2])
 return {"verification":"VERIFIED","away_tricode":a,"home_tricode":h,"away_name":str(g.get("away_name") or a),"home_name":str(g.get("home_name") or h),"game_date_phoenix":str(g.get("game_date_phoenix") or ""),"tip_phoenix":str(g.get("tip_phoenix") or ""),"status":str(g.get("status") or "UPCOMING"),"sportsbook_count":len(verified),"consensus_away_spread":float(median([x[1] for x in verified])),"consensus_home_spread":float(median([x[2] for x in verified])),"best_away":{"sportsbook":ba[0],"spread":ba[1]},"best_home":{"sportsbook":bh[0],"spread":bh[2]},"fabrication":False,"page_wide_source_authority":False}
def resolve_spread_market_route(*,registry:Mapping[str,Any]|None=None,router_policy:Mapping[str,Any]|None=None)->dict[str,Any]:
 reg=dict(registry) if registry is not None else load_registry(_PROVIDER_REGISTRY_PATH); policy=dict(router_policy) if router_policy is not None else load_router_policy(_FIELD_ROUTER_PATH); return route_field(reg,policy,sport="nba",field="sportsbook_lines")
def load_spread_market_features(schedule_games):
 try: route=resolve_spread_market_route()
 except (OSError,TypeError,ValueError):return {"verification":"UNAVAILABLE","diagnostic_state":"SPORTSBOOK_ROUTE_UNAVAILABLE","semantic_metric_id":"SPORTSBOOK_LINES","fabrication":False,"page_wide_source_authority":False}
 if route.get("status")!="ROUTE_READY":return {"verification":"UNAVAILABLE","diagnostic_state":"SPORTSBOOK_ROUTE_UNAVAILABLE","semantic_metric_id":"SPORTSBOOK_LINES","fabrication":False,"page_wide_source_authority":False}
 transport=load_verified_sportsbook_observations(schedule_games)
 if transport.get("verification")!="VERIFIED":return {**transport,"semantic_metric_id":"SPORTSBOOK_LINES","route_id":route.get("route_id")}
 result=build_spread_market_context(transport.get("observations") or [],schedule_games); result.update({"semantic_metric_id":"SPORTSBOOK_LINES","route_id":route.get("route_id"),"active_provider_ids":["direct_sportsbook_feed"]}); return result
__all__=["MODEL_VERSION","MARKET_SECTION_LABEL","SPORTSBOOK_PROJECTION_INFLUENCE","MAY_ACTIVATE_MARKET_LINES","MAY_ACTIVATE_INJURIES","MAY_MODIFY_MODEL","MAY_MODIFY_PROJECTION","MAY_MODIFY_PROBABILITY","MAY_ACTIVATE_RANKING","build_spread_market_context","resolve_spread_market_route","load_spread_market_features"]
