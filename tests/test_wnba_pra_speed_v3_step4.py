from __future__ import annotations

from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]
API_CACHE = ROOT / "sports_api" / "api" / "wnba_pra_cached_detail_bundle.py"
STEP4 = ROOT / "wnba_pra_speed_v3_step4_cache.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4.py"
PUBLIC = ROOT / "devsystem" / "wnba_pra_speed_v3_step4_public_profile.py"
API_MAIN = ROOT / "sports_api" / "main.py"
APP = ROOT / "app.py"


def _step3_bundle(player_id: int = 123, season: int = 2026):
    return {
        "data_type": "wnba_pra_speed_v3_step3_detail_bundle",
        "schema_version": "wnba_pra_speed_v3_step3_detail_bundle_v1",
        "player_id": player_id,
        "season": season,
        "consumer": {"board": {"available": True}},
        "history": {"player_id": player_id, "games": [{"game_id": "1"}]},
        "consumer_error": "",
        "history_error": "",
    }


def test_step4_surfaces_exist():
    assert API_CACHE.exists()
    assert STEP4.exists()
    assert ROUTER.exists()
    assert PUBLIC.exists()


def test_step4_server_cache_hits_finished_bundle_once(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_cached_detail_bundle")
    module._CACHE.clear()
    module._KEY_LOCKS.clear()
    calls = {"count": 0}

    def fake_builder(player_id, season):
        calls["count"] += 1
        return _step3_bundle(player_id, season)

    monkeypatch.setattr(module, "build_pra_detail_bundle", fake_builder)

    first = module.get_cached_pra_detail_bundle(123, 2026)
    second = module.get_cached_pra_detail_bundle(123, 2026)

    assert calls["count"] == 1
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert first["bundle"] == second["bundle"]
    assert second["bundle"]["data_type"] == "wnba_pra_speed_v3_step3_detail_bundle"
    assert second["semantics"]["frozen_step3_bundle_changed"] is False


def test_step4_does_not_cache_partial_bundle(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_cached_detail_bundle")
    module._CACHE.clear()
    module._KEY_LOCKS.clear()
    calls = {"count": 0}

    def fake_builder(player_id, season):
        calls["count"] += 1
        value = _step3_bundle(player_id, season)
        value["history"] = None
        value["history_error"] = "UpstreamError"
        return value

    monkeypatch.setattr(module, "build_pra_detail_bundle", fake_builder)

    first = module.get_cached_pra_detail_bundle(123, 2026)
    second = module.get_cached_pra_detail_bundle(123, 2026)

    assert calls["count"] == 2
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is False


def test_step4_streamlit_loader_unwraps_cached_step3_bundle(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step4_cache")
    observed = {}

    outer = {
        "data_type": module.EXPECTED_DATA_TYPE,
        "schema_version": module.EXPECTED_SCHEMA_VERSION,
        "player_id": 123,
        "season": 2026,
        "bundle": _step3_bundle(),
        "cache": {"hit": True, "generation_ms": 0.0},
    }

    monkeypatch.setattr(module, "_read_cached_bundle", lambda player_id: outer)
    monkeypatch.setattr(module, "normalize_consumer_payload", lambda value: {"normalized": True})
    monkeypatch.setattr(module, "_record", lambda **values: observed.update(values))

    result = module.load_cached_bundle_pair("game-1", 123)

    assert result["consumer"] == {"normalized": True}
    assert result["history"]["player_id"] == 123
    assert result["network_reads"] == 1
    assert result["step4_server_cache_hit"] is True
    assert observed["server_cache_hit"] is True
    assert observed["streamlit_network_reads"] == 1


def test_step4_router_is_forward_only_and_restores_step3_symbol():
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8 as frozen_parent" in source
    assert "wnba_pra_speed_v3_step3_bundle as frozen_step3_bundle" in source
    assert "original_loader = frozen_step3_bundle.load_bundle_pair" in source
    assert "frozen_step3_bundle.load_bundle_pair = step4_cache.load_cached_bundle_pair" in source
    assert "frozen_step3_bundle.load_bundle_pair = original_loader" in source
    assert "finally:" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source


def test_step4_activation_is_wired():
    api_source = API_MAIN.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")
    assert "from sports_api.api.wnba_pra_cached_detail_bundle import router as wnba_pra_cached_detail_bundle_router" in api_source
    assert "app.include_router(wnba_pra_cached_detail_bundle_router)" in api_source
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step4 import record_bootstrap_import_ms, render_app" in app_source


def test_step4_contract_targets_original_speed_budget():
    module = importlib.import_module("wnba_pra_speed_v3_step4_cache")
    contract = module.CACHE_CONTRACT
    assert contract["warm_same_session_target_seconds_max"] == 0.75
    assert contract["cached_cold_player_target_seconds_max"] == 1.5
    assert contract["true_cold_pra_target_seconds_max"] == 2.5
    assert contract["frozen_speed_v3_steps_1_3_modified"] is False
