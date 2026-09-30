from __future__ import annotations

from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "sports_api" / "api" / "wnba_pra_speed_v3_step5_fast_history.py"
STEP5 = ROOT / "wnba_pra_speed_v3_step5_consumer_reuse.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step5.py"
PUBLIC = ROOT / "devsystem" / "wnba_pra_speed_v3_step5_public_profile.py"
API_MAIN = ROOT / "sports_api" / "main.py"
APP = ROOT / "app.py"


def _consumer():
    return {"data_type": "wnba_step18a_streamlit_consumer_latest", "board": {"available": True}}


def _history(player_id=123):
    return {
        "data_type": "official_player_game_log",
        "player_id": int(player_id),
        "games": [{"game_id": "1"}],
    }


def test_step5_surfaces_exist():
    assert API.exists()
    assert STEP5.exists()
    assert ROUTER.exists()
    assert PUBLIC.exists()


def test_step5_fast_history_wraps_frozen_step3_transport(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_speed_v3_step5_fast_history")
    calls = []

    def fake_history(player_id, season):
        calls.append((player_id, season))
        return _history(player_id)

    monkeypatch.setattr(module, "get_step3_espn_player_game_log_dataset", fake_history)
    payload = module.get_fast_pra_history(123, 2026)

    assert calls == [(123, 2026)]
    assert payload["history"]["player_id"] == 123
    assert payload["semantics"]["consumer_snapshot_read"] is False
    assert payload["semantics"]["new_history_cache_added"] is False
    assert payload["semantics"]["frozen_step3_history_transport_reused"] is True


def test_step5_cross_player_reuses_consumer_and_reads_only_history(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step5_consumer_reuse")
    observed = {}

    monkeypatch.setattr(module.performance, "_cached_consumer", lambda: _consumer())
    monkeypatch.setattr(module.performance, "_cached_history", lambda player_id: None)
    monkeypatch.setattr(
        module.performance,
        "_FROZEN_PLAYER_LOADER",
        lambda game_id, player_id: (_ for _ in ()).throw(AssertionError("cold pair must not run")),
    )
    monkeypatch.setattr(module, "_read_fast_history", lambda player_id: _history(player_id))
    monkeypatch.setattr(module.performance, "_cache_history", lambda player_id, value: None)
    monkeypatch.setattr(module, "_record", lambda **values: observed.update(values))

    result = module.load_player_intelligence_cross_player_reuse("game-1", 456)

    assert result["consumer"]["board"]["available"] is True
    assert result["history"]["player_id"] == 456
    assert result["network_reads"] == 1
    assert result["reuse"]["consumer_session_hit"] is True
    assert result["reuse"]["history_session_hit"] is False
    assert result["reuse"]["consumer_network_reads"] == 0
    assert result["reuse"]["history_network_reads"] == 1
    assert result["reuse"]["fast_history_used"] is True
    assert observed["duplicate_consumer_read_suppressed"] is True


def test_step5_true_cold_delegates_to_frozen_step4_loader(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step5_consumer_reuse")
    cached = {"consumer": None, "history": None}
    monkeypatch.setattr(module.performance, "_cached_consumer", lambda: None)
    monkeypatch.setattr(module.performance, "_cached_history", lambda player_id: None)
    monkeypatch.setattr(
        module.performance,
        "_FROZEN_PLAYER_LOADER",
        lambda game_id, player_id: {
            "consumer": _consumer(),
            "history": _history(player_id),
            "consumer_error": "",
            "history_error": "",
        },
    )
    monkeypatch.setattr(
        module.performance,
        "_cache_consumer",
        lambda value: cached.__setitem__("consumer", value),
    )
    monkeypatch.setattr(
        module.performance,
        "_cache_history",
        lambda player_id, value: cached.__setitem__("history", value),
    )
    monkeypatch.setattr(module, "_record", lambda **values: None)

    result = module.load_player_intelligence_cross_player_reuse("game-1", 123)

    assert result["network_reads"] == 1
    assert result["reuse"]["cold_pair_loader_used"] is True
    assert result["reuse"]["fast_history_used"] is False
    assert cached["consumer"]["board"]["available"] is True
    assert cached["history"]["player_id"] == 123


def test_step5_warm_same_player_is_zero_read(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step5_consumer_reuse")
    monkeypatch.setattr(module.performance, "_cached_consumer", lambda: _consumer())
    monkeypatch.setattr(module.performance, "_cached_history", lambda player_id: _history(player_id))
    monkeypatch.setattr(module, "_record", lambda **values: None)

    result = module.load_player_intelligence_cross_player_reuse("game-1", 123)

    assert result["network_reads"] == 0
    assert result["reuse"]["consumer_session_hit"] is True
    assert result["reuse"]["history_session_hit"] is True
    assert result["reuse"]["fast_history_used"] is False


def test_step5_router_is_forward_only_and_restores_loader():
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9 as current_parent" in source
    assert "performance.load_player_intelligence_same_session" in source
    assert "step5.load_player_intelligence_cross_player_reuse" in source
    assert "finally:" in source
    assert "performance.load_player_intelligence_same_session = original_loader" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source


def test_step5_activation_is_wired():
    api_source = API_MAIN.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")
    assert "wnba_pra_speed_v3_step5_fast_history_router" in api_source
    assert "app.include_router(wnba_pra_speed_v3_step5_fast_history_router)" in api_source
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step5 import record_bootstrap_import_ms, render_app" in app_source


def test_step5_contract_preserves_speed_budget_and_history_cache_ownership():
    module = importlib.import_module("wnba_pra_speed_v3_step5_consumer_reuse")
    contract = module.REUSE_CONTRACT
    assert contract["warm_same_session_target_seconds_max"] == 0.75
    assert contract["cached_cold_player_target_seconds_max"] == 1.5
    assert contract["true_cold_pra_target_seconds_max"] == 2.5
    assert contract["consumer_reads_on_cross_player_open_max"] == 0
    assert contract["history_reads_on_cross_player_open_max"] == 1
    assert contract["new_history_cache_added"] is False
    assert contract["frozen_speed_v3_steps_1_4_modified"] is False
