"""NBA PRA Page 1 multi-source aggregator.

SportsGameOdds + Odds-API.io PRA markets, ESPN NBA player data, and the existing
verified NBA schedule/injury ownership. All failures fail closed.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any, Mapping
from nba_pra_page1_common_v1 import MODEL_VERSION, SPORTSBOOK_PROJECTION_INFLUENCE, _text, _norm, nba_season_end_year, phoenix_date, select_next_active_slate
from nba_pra_page1_sgo_v1 import build_sgo_odd_id_filter, parse_sgo_event_props, load_sgo_pra_observations
from nba_pra_page1_odds_v1 import normalize_odds_api_pra, load_odds_api_pra_observations, reconcile_pra_market
from nba_pra_page1_history_v1 import normalize_espn_roster, normalize_espn_gamelog, load_espn_roster, load_espn_gamelog, build_player_profiles

def flatten_injury_players(payload: Mapping[str,Any])->dict[str,dict[str,Any]]:
    out={}
    for feature in payload.get("features",[]) or []:
        if not isinstance(feature,Mapping): continue
        for side in ("away","home"):
            block=feature.get(side) or {}
            for player in block.get("players",[]) if isinstance(block,Mapping) else []:
                if isinstance(player,Mapping) and _text(player.get("player_name")):
                    out[_norm(player["player_name"])]=dict(player,verification=feature.get("verification"),providers_consulted=feature.get("providers_consulted") or [])
    return out

def load_page1_snapshot(*, now: datetime|None=None)->dict[str,Any]:
    from nba_spread_schedule_provider_resilience_step2_r1 import load_verified_nba_schedule
    from nba_spread_injury_availability_v1 import load_injury_availability_features
    now=now or datetime.now(timezone.utc); schedule=load_verified_nba_schedule(now_utc=now); all_games=list(schedule.get("games") or []); today=phoenix_date(now); slate_date_text,games=select_next_active_slate(all_games,today)
    if not slate_date_text: return {"verification":schedule.get("verification","UNAVAILABLE"),"slate_date":None,"games":[],"market":{},"profiles":{},"injury_players":{},"sources":{"schedule":schedule}}
    slate_date=date.fromisoformat(slate_date_text); sgo=load_sgo_pra_observations(slate_date); odds=load_odds_api_pra_observations(slate_date); market=reconcile_pra_market(sgo,odds)
    try: injury_payload=load_injury_availability_features(games,now_utc=now)
    except Exception: injury_payload={"verification":"UNAVAILABLE","features":[]}
    return {"verification":schedule.get("verification","UNAVAILABLE"),"slate_date":slate_date_text,"games":games,"market":market,"profiles":build_player_profiles(games,market,slate_date) if market else {},"injury_players":flatten_injury_players(injury_payload),"sources":{"schedule":schedule,"sgo":sgo,"odds_api":odds,"injuries":injury_payload}}
