from __future__ import annotations

from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]
STEP7 = ROOT / "wnba_pra_speed_v3_step7_precompute.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step7.py"
APP = ROOT / "app.py"

FROZEN_STEP6 = {
    "wnba_pra_speed_v3_step6_history_cache.py": "ac5b541f1101bbafdec37ced59d0404ffc13ff89",
    "streamlit_memory_lazy_router_wnba_pra_speed_v3_step6.py": "e5bd4bc9db75982d2cf0ce886e48053d1c84acc2",
    "sports_api/api/wnba_pra_speed_v3_step6_history_cache.py": "4acfdf62dbcffc5f86c3f6ef8c2faa03b23458b2",
}


def _blob(path: Path) -> str:
    import subprocess
    return subprocess.check_output(
        ["git", "hash-object", str(path)],
        cwd=ROOT,
        text=True,
    ).strip()


def test_step7_surfaces_exist():
    assert STEP7.exists()
    assert ROUTER.exists()


def test_step7_contract_is_nonblocking_precompute_only():
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    contract = module.PRECOMPUTE_CONTRACT
    assert contract["step"] == "7/9"
    assert contract["background"] is True
    assert contract["navigation_callback_blocking"] is False
    assert contract["target_endpoint"].endswith("/pra-detail-cached")
    assert contract["max_workers"] == 4
    assert contract["per_player_transport_attempts"] == 2
    assert contract["frozen_speed_v3_steps_1_6_modified"] is False
    assert contract["projection_math_changed"] is False
    assert contract["market_math_changed"] is False
    assert contract["sportsbook_projection_influence"] == 0.0


def test_step7_extracts_unique_verified_game_center_players():
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    payload = {
        "teams": {
            "1": [
                {"player_id": 101},
                {"player_id": 102},
                {"player_id": 101},
                {"player_id": None},
            ],
            "2": [
                {"player_id": "201"},
                {"player_id": 0},
                {"player_id": "bad"},
            ],
        }
    }
    assert module.active_player_ids(payload) == [101, 102, 201]


def test_step7_scheduler_dedupes_without_waiting(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    module._LAST_SCHEDULED.clear()
    module._FUTURES.clear()
    submitted = []

    class FakeFuture:
        def done(self):
            return False

    class FakeExecutor:
        def submit(self, fn, pid):
            submitted.append((fn, pid))
            return FakeFuture()

    monkeypatch.setattr(module, "_EXECUTOR", FakeExecutor())
    payload = {"teams": {"1": [{"player_id": 101}, {"player_id": 102}]}}
    first = module.schedule_precompute(payload)
    second = module.schedule_precompute(payload)

    assert first["target_players"] == 2
    assert first["scheduled"] == 2
    assert second["scheduled"] == 0
    assert second["already_running"] == 2
    assert [pid for _, pid in submitted] == [101, 102]


def test_step7_warmer_uses_frozen_step4_cached_detail_endpoint(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    observed = {}

    class FakeClient:
        def __init__(self, **kwargs):
            observed["kwargs"] = kwargs

        def get_json(self, path, params=None):
            observed["path"] = path
            observed["params"] = params
            return {
                "data_type": module.EXPECTED_DATA_TYPE,
                "schema_version": module.EXPECTED_SCHEMA_VERSION,
                "player_id": 101,
                "season": int(module.SUPPORTED_SEASON),
                "bundle": {
                    "player_id": 101,
                    "season": int(module.SUPPORTED_SEASON),
                    "consumer": {"rows": []},
                    "history": {"player_id": 101, "season": int(module.SUPPORTED_SEASON), "games": []},
                    "consumer_error": "",
                    "history_error": "",
                },
                "cache": {"hit": False},
            }

    monkeypatch.setattr(module, "KyreWNBAAPIClient", FakeClient)
    result = module._warm_one(101)

    assert observed["kwargs"]["attempts"] == 2
    assert observed["kwargs"]["timeout_seconds"] == module.API_TIMEOUT_SECONDS
    assert observed["path"].endswith("/101/pra-detail-cached")
    assert observed["params"] == {"season": module.SUPPORTED_SEASON}
    assert result["status"] == "green"


def test_step7_router_wraps_frozen_step6_only():
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_wnba_pra_speed_v3_step6 as frozen_parent" in source
    assert "step7.render_step7_route(frozen_parent.render_app)" in source
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step6"' in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source


def test_step7_activation_is_wired():
    source = APP.read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step7 import record_bootstrap_import_ms, render_app" in source
    assert "Frozen WNBA PRA Speed V3 Step 6 compatibility" in source


def test_step7_freezes_step6_owner_blobs():
    for path, expected in FROZEN_STEP6.items():
        assert _blob(ROOT / path) == expected, path
