from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def test_loader_v24_overrides_only_nba_spread_and_delegates_other_routes(monkeypatch):
    loader = importlib.import_module("universal_runtime_v5_loader_v24")

    nba_route = SimpleNamespace(sport_id="nba", market_id="spread")
    nfl_route = SimpleNamespace(sport_id="nfl", market_id="spread")

    nba_adapter = loader.resolve_destination(nba_route)
    assert "NBA SPREAD PAGE1 DECISION BOARD V1" in loader.MODEL_VERSION
    assert nba_adapter.source_version == loader.MODEL_VERSION

    prior = importlib.import_module("universal_runtime_v5_loader_v23")
    prior_adapter = prior.resolve_destination(nfl_route)
    current_adapter = loader.resolve_destination(nfl_route)
    assert current_adapter.route_key == prior_adapter.route_key
    assert current_adapter.source_version == prior_adapter.source_version


def test_terminal_v7_binds_loader_v24_and_preserves_frozen_runtime():
    terminal = importlib.import_module("streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7")
    assert "NBA SPREAD PAGE1 DECISION BOARD V1" in terminal.MODEL_VERSION
    assert terminal.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert terminal.MAY_MODIFY_PROJECTION is False
    assert terminal.FROZEN_RUNTIME == "streamlit_memory_lazy_router_universal_runtime_v5"


def test_production_entrypoint_uses_terminal_v7_only():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7" in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v6" not in source


def test_opener_verifier_and_runless_plan_exist_with_required_scope():
    verifier = ROOT / "devsystem" / "verify_nba_spread_page1_opener_v1.py"
    plan = ROOT / "devsystem" / "runless_proof_plans" / "api2-nba-spread-page1-decision-board-v1.json"
    assert verifier.exists()
    assert plan.exists()
    text = verifier.read_text(encoding="utf-8")
    assert "BOS@DET" in text and "PHI@NYK" in text and "OKC@SAS" in text
    assert "credential_resolver" in text
    assert "live_v2.resolve_sgo_api_key" in text
    assert "credential material is never printed or returned" in text
    plan_text = plan.read_text(encoding="utf-8")
    assert "API2_NBA_SPREAD_PAGE1_DECISION_BOARD_V1_FROZEN" in plan_text
    assert "test_api2_nba_spread_runtime_integration_v1.py" in plan_text
    assert "api2_universal_runtime_v5_cert" in plan_text
