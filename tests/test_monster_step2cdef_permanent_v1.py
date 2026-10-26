from __future__ import annotations

import copy
import importlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _require_module(name: str):
    spec = importlib.util.find_spec(name)
    assert spec is not None, f"missing permanent MONSTER module: {name}"
    return importlib.import_module(name)


def test_canonical_registry_and_terminal_router_have_no_orphans():
    registry = importlib.import_module("universal_sports_nav_registry_v1")
    state = importlib.import_module("universal_runtime_v5_state")
    terminal = importlib.import_module("streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1")

    assert registry.get_market("nba", "pra") is not None
    assert "prop" in registry.get_market("cfb", "player-props").page_params

    for sport in registry.visible_sports():
        for market in sport.markets:
            if not market.live:
                continue
            route = state.RuntimeRoute(sport.id, market.id, {}, 1, "monster-step2e-test")
            adapter = terminal.resolve_destination(route)
            assert adapter.route_key == (sport.id, market.id)
            assert not str(adapter.source_version).startswith("fail-closed:")
            assert callable(adapter.loader)
            assert callable(adapter.renderer)

    cfb_props = terminal.resolve_destination(
        state.RuntimeRoute("cfb", "player-props", {"game_id": "g", "player_id": "p", "prop": "passing-yards"}, 1, "monster-step2e-test")
    )
    assert "cfb_player_props_runtime_v3" in cfb_props.source_version.lower()


def test_terminal_control_labels_are_monster_owned():
    app = (ROOT / "app.py").read_text(encoding="utf-8").lower()
    terminal = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py").read_text(encoding="utf-8").lower()
    heartbeat = next(line for line in app.splitlines() if "_streamlit_deployment_heartbeat" in line)
    model = next(line for line in terminal.splitlines() if line.startswith("model_version"))
    assert "monster" in heartbeat and "api2" not in heartbeat and "api 2" not in heartbeat
    assert "monster" in model and "api2" not in model and "api 2" not in model


def test_step2e_repository_audit_is_green():
    gate = _require_module("devsystem.mandatory_2e_router_ownership_gate_v1")
    result = gate.verify_repository_routes(ROOT)
    assert result["status"] == "GREEN"
    assert result["monster_only"] is True
    assert result["orphan_frontend_routes"] == []
    assert result["unregistered_terminal_routes"] == []
    assert result["foreign_owner_labels"] == []
    assert result["route_count"] >= 1


def _production_evidence():
    sha = "a" * 40
    return {
        "system": "MONSTER",
        "certified_head_sha": sha,
        "deployment": {
            "id": "dpl_monster_exact",
            "target": "production",
            "state": "READY",
            "git_sha": sha,
            "branch": "monster-main",
            "url": "https://monster-proof.example",
        },
        "stable_alias": {
            "url": "https://monster-stable.example",
            "deployment_id": "dpl_monster_exact",
            "git_sha": sha,
        },
        "canonical_endpoint": {
            "url": "https://monster-stable.example/health",
            "status_code": 200,
            "router_owner": "MONSTER",
            "schema_owner": "MONSTER",
            "git_sha": sha,
        },
        "website": {
            "url": "https://site.example",
            "status_code": 200,
            "consumed_sha": sha,
            "route_smokes": [
                {"route": "nba/pra", "status": "PASS"},
                {"route": "cfb/player-props", "status": "PASS"},
            ],
        },
        "rollback_anchor": {"deployment_id": "dpl_monster_previous", "git_sha": "b" * 40},
        "proof": {"proof_id": "monster-proof-1", "receipt_digest": "c" * 64},
    }


def test_step2f_requires_exact_production_alias_and_live_consumption():
    gate = _require_module("devsystem.mandatory_2f_live_production_gate_v1")
    good = gate.verify_live_production(_production_evidence())
    assert good["status"] == "GREEN"
    assert good["exact_head_deployment"] is True
    assert good["stable_alias_parity"] is True
    assert good["website_consumes_exact_head"] is True

    for path, value in (
        (("deployment", "target"), "preview"),
        (("deployment", "git_sha"), "d" * 40),
        (("stable_alias", "deployment_id"), "dpl_wrong"),
        (("website", "consumed_sha"), "e" * 40),
    ):
        bad = copy.deepcopy(_production_evidence())
        bad[path[0]][path[1]] = value
        with pytest.raises(gate.Mandatory2FLiveProductionFailure):
            gate.verify_live_production(bad)


def test_permanent_control_stack_order_and_recovery_are_locked():
    stack = _require_module("devsystem.monster_permanent_control_stack_v1")
    assert stack.CONTROL_ORDER == (
        "STEP_2A", "ANTI_LOOP", "STEP_2C", "STEP_2B", "EXECUTE",
        "STEP_2D", "STEP_2E", "STEP_2F", "FINAL_VERIFY", "GREEN", "FROZEN",
    )
    assert stack.FAILURE_RECOVERY == (
        "ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "CORRECTED_EXECUTION",
        "STEP_2D", "STEP_2E", "STEP_2F",
    )
    result = stack.contract_self_test(ROOT)
    assert result["status"] == "GREEN"
    assert result["monster_only"] is True
    assert result["step2d_wired"] is True
    assert result["step2e_wired"] is True
    assert result["step2f_wired"] is True
