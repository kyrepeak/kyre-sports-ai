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
    assert contract["max_workers"] == 2
    assert contract["foreground_headroom_reserved"] is True
    assert contract["precompute_order"] == "game_center_display_order"
    assert contract["eligibility_gate"] == "existing_v2_8_pra_gate"
    assert contract["ineligible_designations"] == ["DOUBTFUL", "INACTIVE", "OUT"]
    assert contract["min_projected_minutes"] == 15.0
    assert contract["per_player_transport_attempts"] == 2
    assert contract["invalid_bundle_retry_max"] == 1
    assert contract["invalid_bundle_retry_delay_seconds"] == 0.15
    assert contract["frozen_speed_v3_steps_1_6_modified"] is False
    assert contract["projection_math_changed"] is False
    assert contract["market_math_changed"] is False
    assert contract["sportsbook_projection_influence"] == 0.0


def test_step7_extracts_only_unique_pra_eligible_active_players():
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    payload = {
        "teams": {
            "1": [
                {"player_id": 101, "projected_minutes": 32.0, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
                {"player_id": 102, "projected_minutes": 18.0, "designation": "QUESTIONABLE", "role_label": "STATUS UNCERTAIN"},
                {"player_id": 101, "projected_minutes": 32.0, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
                {"player_id": 103, "projected_minutes": 0.0, "designation": "OUT", "role_label": "OUT"},
                {"player_id": 104, "projected_minutes": 14.9, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
                {"player_id": None, "projected_minutes": 25.0, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
            ],
            "2": [
                {"player_id": "201", "projected_minutes": 24.0, "designation": "PROBABLE", "role_label": "STATUS UNCERTAIN"},
                {"player_id": 202, "projected_minutes": 22.0, "designation": "INACTIVE", "role_label": "OUT"},
                {"player_id": "bad", "projected_minutes": 30.0, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
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
    payload = {"teams": {"1": [
        {"player_id": 101, "projected_minutes": 32.0, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
        {"player_id": 102, "projected_minutes": 28.0, "designation": "NO DESIGNATION", "role_label": "ACTIVE"},
    ]}}
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


def test_step7_retries_one_incomplete_http200_bundle(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    calls = {"count": 0}
    valid = {
        "data_type": module.EXPECTED_DATA_TYPE,
        "schema_version": module.EXPECTED_SCHEMA_VERSION,
        "player_id": 101,
        "season": int(module.SUPPORTED_SEASON),
        "bundle": {
            "player_id": 101,
            "season": int(module.SUPPORTED_SEASON),
            "consumer": {"rows": []},
            "history": {
                "player_id": 101,
                "season": int(module.SUPPORTED_SEASON),
                "games": [],
            },
            "consumer_error": "",
            "history_error": "",
        },
        "cache": {"hit": True},
    }

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["attempts"] == 2

        def get_json(self, path, params=None):
            calls["count"] += 1
            if calls["count"] == 1:
                broken = dict(valid)
                broken["bundle"] = dict(valid["bundle"])
                broken["bundle"]["history_error"] = "TransientHistory"
                return broken
            return valid

    monkeypatch.setattr(module, "KyreWNBAAPIClient", FakeClient)
    monkeypatch.setattr(module, "sleep", lambda _: None)
    result = module._warm_one(101)

    assert calls["count"] == 2
    assert result["status"] == "green"
    assert result["invalid_bundle_retries"] == 1
    assert result["error"] == ""


def test_step7_invalid_bundle_retry_is_bounded(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step7_precompute")
    calls = {"count": 0}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def get_json(self, path, params=None):
            calls["count"] += 1
            return {
                "data_type": module.EXPECTED_DATA_TYPE,
                "schema_version": module.EXPECTED_SCHEMA_VERSION,
                "player_id": 101,
                "season": int(module.SUPPORTED_SEASON),
                "bundle": {
                    "player_id": 101,
                    "season": int(module.SUPPORTED_SEASON),
                    "consumer": {},
                    "history": {},
                    "consumer_error": "",
                    "history_error": "StillIncomplete",
                },
                "cache": {"hit": False},
            }

    monkeypatch.setattr(module, "KyreWNBAAPIClient", FakeClient)
    monkeypatch.setattr(module, "sleep", lambda _: None)
    result = module._warm_one(101)

    assert calls["count"] == 2
    assert result["status"] == "error"
    assert result["invalid_bundle_retries"] == 1
    assert result["error"] == "ValueError"


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


def test_step7_deployment_refresh_heartbeat_is_permanent():
    source = APP.read_text(encoding="utf-8")
    assert (
        'WNBA_PRA_SPEED_V3_STEP7_PUBLIC_DEPLOY_REFRESH = '
        '"WNBA_PRA_SPEED_V3_STEP7_PUBLIC_DEPLOY_REFRESH_2026_09_30_R1"'
        in source
    )
    assert (
        "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step7 "
        "import record_bootstrap_import_ms, render_app"
        in source
    )


def test_step7_freezes_step6_owner_blobs():
    for path, expected in FROZEN_STEP6.items():
        assert _blob(ROOT / path) == expected, path
