from __future__ import annotations

from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]
API_ROUTE = ROOT / "sports_api" / "api" / "wnba_pra_detail_bundle.py"
STEP3 = ROOT / "wnba_pra_speed_v3_step3_bundle.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step3.py"
PUBLIC = ROOT / "devsystem" / "wnba_pra_speed_v3_step3_public_profile.py"
MAIN = ROOT / "sports_api" / "main.py"
APP = ROOT / "app.py"


def test_step3_surfaces_exist():
    assert API_ROUTE.exists(), "Step-3 backend PRA detail bundle route is missing"
    assert STEP3.exists(), "Step-3 Streamlit bundle loader is missing"
    assert ROUTER.exists(), "Step-3 router is missing"
    assert PUBLIC.exists(), "Step-3 public proof is missing"


def test_step3_backend_bundle_uses_same_certified_sources():
    source = API_ROUTE.read_text(encoding="utf-8")
    assert '@router.get("/players/{player_id}/pra-detail")' in source
    assert "ThreadPoolExecutor(max_workers=2)" in source
    assert "build_step18a_consumer_latest" in source
    assert "get_player_game_log_dataset" in source
    assert '"streamlit_hosted_reads_required": 1' in source
    assert '"projection_run": False' in source
    assert '"sportsbook_network_called": False' in source
    assert '"monte_carlo_run": False' in source


def test_step3_backend_bundle_preserves_component_payloads(monkeypatch):
    module = importlib.import_module("sports_api.api.wnba_pra_detail_bundle")
    raw_consumer = {"data_type": "wnba_step18a_streamlit_consumer_latest", "board": {"available": True}}
    raw_history = {"data_type": "official_player_game_log", "player_id": 123, "games": [{"game_id": "1"}]}

    monkeypatch.setattr(module, "build_step18a_consumer_latest", lambda: raw_consumer)
    monkeypatch.setattr(
        module,
        "get_player_game_log_dataset",
        lambda player_id, season, season_type="Regular Season": raw_history,
    )

    result = module.build_pra_detail_bundle(123, 2026)
    assert result["consumer"] == raw_consumer
    assert result["history"] == raw_history
    assert result["consumer_error"] == ""
    assert result["history_error"] == ""
    assert result["player_id"] == 123
    assert result["season"] == 2026
    assert result["semantics"]["streamlit_hosted_reads_required"] == 1


def test_step3_streamlit_bundle_normalizes_consumer_and_reports_one_read(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step3_bundle")
    raw_consumer = {"data_type": "wnba_step18a_streamlit_consumer_latest", "board": {"available": True}}
    normalized = {"state": "ready", "cards": [{"player_id": 123}]}
    history = {"data_type": "official_player_game_log", "player_id": 123, "games": []}
    body = {
        "data_type": module.EXPECTED_DATA_TYPE,
        "schema_version": module.EXPECTED_SCHEMA_VERSION,
        "player_id": 123,
        "season": 2026,
        "consumer": raw_consumer,
        "history": history,
        "consumer_error": "",
        "history_error": "",
    }
    monkeypatch.setattr(module, "_read_bundle", lambda player_id: body)
    monkeypatch.setattr(module, "normalize_consumer_payload", lambda value: normalized)

    payload = module.load_bundle_pair("game-1", 123)
    assert payload["consumer"] == normalized
    assert payload["history"] == history
    assert payload["network_reads"] == 1
    assert payload["projection_runs"] == 0
    assert payload["sportsbook_calls"] == 0
    assert payload["ranking_runs"] == 0
    assert payload["monte_carlo_runs"] == 0


def test_step3_router_intercepts_only_frozen_cold_pair_loader():
    source = ROUTER.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_wnba_pra_speed_v3_step2 as frozen_step2" in source
    assert "import wnba_pra_performance_v2_step5 as performance" in source
    assert "original_cold_loader = performance._FROZEN_PLAYER_LOADER" in source
    assert "performance._FROZEN_PLAYER_LOADER = bundle.load_bundle_pair" in source
    assert "performance._FROZEN_PLAYER_LOADER = original_cold_loader" in source
    assert "finally:" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source


def test_step3_backend_router_and_streamlit_activation_are_wired():
    main_source = MAIN.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")
    assert "from sports_api.api.wnba_pra_detail_bundle import router as wnba_pra_detail_bundle_router" in main_source
    assert "app.include_router(wnba_pra_detail_bundle_router)" in main_source
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step3 import record_bootstrap_import_ms, render_app" in app_source
    assert "Frozen WNBA PRA Speed V3 Step 2 compatibility" in app_source
