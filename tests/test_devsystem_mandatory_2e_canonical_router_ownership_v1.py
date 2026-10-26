from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem/mandatory_2e_canonical_router_ownership_v1.py"
    assert path.is_file(), "Step 2E production module missing"
    spec = importlib.util.spec_from_file_location("mandatory_2e_canonical_router_ownership_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _registry():
    return {"version":"MONSTER_ROUTER_REGISTRY_V1","routes":[{"sport_id":"nfl","market_id":"passing-yards","frontend_module":"nfl_passing_yards_simple_qb_grid_v1","consumer_owner":"nfl_passing_yards_simple_qb_grid_v1","required_params":["date","game_id","player_id"],"backend_required":False},{"sport_id":"cfb","market_id":"game-total","frontend_module":"cfb_game_total_page1_daily_slate_v1","consumer_owner":"cfb_game_total_page1_daily_slate_v1+cfb_game_total_page2_market_completeness_r1","required_params":["date","game_id"],"backend_required":True,"backend_endpoint":"/api/v1/cfb/odds","backend_router":"cfb_markets_router"}]}


def _evidence():
    return {"live_routes":["nfl:passing-yards","cfb:game-total"],"destinations":{"nfl:passing-yards":{"sport_id":"nfl","market_id":"passing-yards","frontend_module":"nfl_passing_yards_simple_qb_grid_v1","consumer_owner":"nfl_passing_yards_simple_qb_grid_v1","preserved_params":["date","game_id","player_id"],"reachable":True,"legacy_override":False,"generic_fallthrough":False},"cfb:game-total":{"sport_id":"cfb","market_id":"game-total","frontend_module":"cfb_game_total_page1_daily_slate_v1","consumer_owner":"cfb_game_total_page1_daily_slate_v1+cfb_game_total_page2_market_completeness_r1","preserved_params":["date","game_id"],"reachable":True,"legacy_override":False,"generic_fallthrough":False}},"backend_mounts":{"/api/v1/cfb/odds":{"router":"cfb_markets_router","mounted":True}}}


def test_step2e_accepts_one_canonical_owner_per_live_route():
    mod=_load(); result=mod.validate_router_registry(_registry(),_evidence())
    assert result["status"]=="GREEN" and result["step2e_enforced"] is True
    assert result["all_live_routes_owned"] is True and result["backend_mounts_verified"] is True
    assert result["final_verification_authorized"] is True


def test_step2e_blocks_duplicate_or_cross_sport_ownership():
    mod=_load(); registry=_registry(); registry["routes"].append(dict(registry["routes"][0]))
    duplicate=mod.validate_router_registry(registry,_evidence())
    assert duplicate["status"]=="BLOCKED" and duplicate["next_legal_action"]=="RETURN_TO_MONSTER_STEP_2C" and duplicate["failure_fingerprint"]
    evidence=_evidence(); evidence["destinations"]["nfl:passing-yards"]["sport_id"]="mlb"
    cross=mod.validate_router_registry(_registry(),evidence)
    assert cross["status"]=="BLOCKED" and cross["failure_kind"]=="CROSS_SPORT_ROUTING"


def test_step2e_blocks_orphans_missing_modules_mounts_params_and_overrides():
    mod=_load(); cases=[]
    evidence=_evidence(); evidence["live_routes"].append("nfl:moneyline"); cases.append(evidence)
    evidence=_evidence(); evidence["destinations"]["nfl:passing-yards"]["frontend_module"]=""; cases.append(evidence)
    evidence=_evidence(); evidence["destinations"]["cfb:game-total"]["preserved_params"]=["date"]; cases.append(evidence)
    evidence=_evidence(); evidence["backend_mounts"]["/api/v1/cfb/odds"]["mounted"]=False; cases.append(evidence)
    evidence=_evidence(); evidence["destinations"]["nfl:passing-yards"]["legacy_override"]=True; cases.append(evidence)
    evidence=_evidence(); evidence["destinations"]["nfl:passing-yards"]["generic_fallthrough"]=True; cases.append(evidence)
    for evidence in cases:
        result=mod.validate_router_registry(_registry(),evidence)
        assert result["status"]=="BLOCKED" and result["final_verification_authorized"] is False


def test_step2e_repository_audit_covers_every_current_live_route():
    mod=_load(); result=mod.audit_current_repository()
    assert result["status"]=="GREEN"
    assert result["repository_audit"] is True
    assert result["route_count"] == 38
    assert len(result["canonical_owners"]) == 38
    assert result["kyre_sports_api_mount_surface"] is True


def test_step2e_contract_self_test_is_green():
    mod=_load(); result=mod.contract_self_test()
    assert result["status"]=="GREEN" and result["monster_only"] is True and result["network_calls"] is False and result["auto_mutate"] is False
