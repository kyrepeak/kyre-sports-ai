from __future__ import annotations

from pathlib import Path
import importlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_CACHE = ROOT / "sports_api" / "api" / "wnba_pra_speed_v3_step6_history_cache.py"
STEP6 = ROOT / "wnba_pra_speed_v3_step6_history_cache.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step6.py"
PUBLIC = ROOT / "devsystem" / "wnba_pra_speed_v3_step6_public_profile.py"
API_MAIN = ROOT / "sports_api" / "main.py"
APP = ROOT / "app.py"


def _history(player_id: int = 123, season: int = 2026):
    return {
        "data_type": "official_player_game_log",
        "season": season,
        "player_id": player_id,
        "games": [{"game_id": "1", "game_date": "2026-09-01"}],
    }


def _step5_source(player_id: int = 123, season: int = 2026):
    return {
        "data_type": "wnba_pra_speed_v3_step5_fast_history",
        "schema_version": "wnba_pra_speed_v3_step5_fast_history_v1",
        "player_id": player_id,
        "season": season,
        "history": _history(player_id, season),
    }


def test_step6_surfaces_exist():
    assert API_CACHE.exists()
    assert STEP6.exists()
    assert ROUTER.exists()
    assert PUBLIC.exists()


def test_step6_server_cache_hits_frozen_step5_source_once(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_speed_v3_step6_history_cache")
    module._CACHE.clear()
    module._KEY_LOCKS.clear()
    calls = {"count": 0}

    def fake_source(player_id, season):
        calls["count"] += 1
        return _step5_source(player_id, season)

    monkeypatch.setattr(module, "get_fast_pra_history", fake_source)

    first = module.get_cached_pra_history(123, 2026)
    second = module.get_cached_pra_history(123, 2026)

    assert calls["count"] == 1
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert first["history"] == second["history"]
    assert second["cache"]["ttl_seconds"] == module.ACTIVE_SEASON_TTL_SECONDS
    assert second["semantics"]["frozen_step5_history_transport_reused"] is True
    assert second["semantics"]["step6_longer_history_cache"] is True


def test_step6_ttl_policy_is_longer_and_season_aware():
    module = importlib.import_module("sports_api.api.wnba_pra_speed_v3_step6_history_cache")
    assert module.ACTIVE_SEASON_TTL_SECONDS == 600
    assert module.HISTORICAL_SEASON_TTL_SECONDS == 21600
    assert module.ACTIVE_SEASON_TTL_SECONDS > 120
    assert module.HISTORICAL_SEASON_TTL_SECONDS > module.ACTIVE_SEASON_TTL_SECONDS
    assert module._ttl_for_season(module.DEFAULT_SEASON) == 600
    assert module._ttl_for_season(module.DEFAULT_SEASON - 1) == 21600


def test_step6_cache_key_is_player_and_season(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_speed_v3_step6_history_cache")
    module._CACHE.clear()
    module._KEY_LOCKS.clear()
    calls = []

    def fake_source(player_id, season):
        calls.append((player_id, season))
        return _step5_source(player_id, season)

    monkeypatch.setattr(module, "get_fast_pra_history", fake_source)

    module.get_cached_pra_history(101, 2026)
    module.get_cached_pra_history(102, 2026)
    module.get_cached_pra_history(101, 2025)
    module.get_cached_pra_history(101, 2026)

    assert calls == [(101, 2026), (102, 2026), (101, 2025)]


def test_step6_does_not_cache_invalid_source(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_speed_v3_step6_history_cache")
    module._CACHE.clear()
    module._KEY_LOCKS.clear()
    calls = {"count": 0}

    def bad_source(player_id, season):
        calls["count"] += 1
        payload = _step5_source(player_id, season)
        payload["history"]["player_id"] = player_id + 1
        return payload

    monkeypatch.setattr(module, "get_fast_pra_history", bad_source)

    with pytest.raises(ValueError):
        module.get_cached_pra_history(123, 2026)
    with pytest.raises(ValueError):
        module.get_cached_pra_history(123, 2026)

    assert calls["count"] == 2
    assert not module._CACHE


def test_step6_streamlit_reader_unwraps_cache_metadata(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step6_history_cache")
    observed = {}

    class FakeClient:
        def __init__(self, **kwargs):
            observed["client_kwargs"] = kwargs

        def get_json(self, path, params=None):
            observed["path"] = path
            observed["params"] = params
            return {
                "data_type": module.EXPECTED_DATA_TYPE,
                "schema_version": module.EXPECTED_SCHEMA_VERSION,
                "player_id": 123,
                "season": 2026,
                "history": _history(123, 2026),
                "cache": {
                    "hit": True,
                    "ttl_seconds": 600,
                    "age_ms": 25.5,
                    "generation_ms": 0.0,
                },
            }

    monkeypatch.setattr(module, "KyreWNBAAPIClient", FakeClient)
    monkeypatch.setattr(module, "_record", lambda **values: observed.update(values))

    history = module.read_cached_history(123)

    assert history["player_id"] == 123
    assert observed["path"].endswith("/123/pra-history-cached")
    assert observed["server_history_cache_hit"] is True
    assert observed["server_history_cache_ttl_seconds"] == 600
    assert observed["history_cache_route_used"] is True


def test_step6_router_preserves_and_restores_step5_reader():
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_wnba_pra_speed_v3_step5 as frozen_parent" in source
    assert "original_history_reader = step5._read_fast_history" in source
    assert "step5._read_fast_history = step6.read_cached_history" in source
    assert "step5._read_fast_history = original_history_reader" in source
    assert "finally:" in source
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step5"' in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source


def test_step6_activation_is_wired():
    api_source = API_MAIN.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")
    assert "from sports_api.api.wnba_pra_speed_v3_step6_history_cache import router as wnba_pra_speed_v3_step6_history_cache_router" in api_source
    assert "app.include_router(wnba_pra_speed_v3_step6_history_cache_router)" in api_source
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step6 import record_bootstrap_import_ms, render_app" in app_source


def test_step6_contract_preserves_original_speed_budget():
    module = importlib.import_module("wnba_pra_speed_v3_step6_history_cache")
    contract = module.HISTORY_CACHE_CONTRACT
    assert contract["warm_same_session_target_seconds_max"] == 0.75
    assert contract["cached_cold_player_target_seconds_max"] == 1.5
    assert contract["true_cold_pra_target_seconds_max"] == 2.5
    assert contract["frozen_speed_v3_steps_1_5_modified"] is False
