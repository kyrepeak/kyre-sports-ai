from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILER_PATH = ROOT / "wnba_pra_speed_v3_step1_profiler.py"
ROUTER_PATH = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step1.py"
APP_PATH = ROOT / "app.py"


def test_speed_v3_step1_profiler_surface_exists():
    assert PROFILER_PATH.exists(), "Step-1 PRA profiler module is missing"
    assert ROUTER_PATH.exists(), "Step-1 PRA profiler router is missing"


def test_speed_v3_step1_profiler_contract_is_measurement_only():
    assert PROFILER_PATH.exists(), "Step-1 PRA profiler module is missing"
    source = PROFILER_PATH.read_text(encoding="utf-8")

    for token in (
        '"projection_math_changed": False',
        '"market_math_changed": False',
        '"sportsbook_projection_influence": 0.0',
        '"network_reads_added": 0',
        '"reruns_added": 0',
        '"model_runs_added": 0',
        '"sportsbook_calls_added": 0',
        '"monte_carlo_runs_added": 0',
        '"frozen_navigation_steps_1_through_7_modified": False',
    ):
        assert token in source

    for timing in (
        "total_render_ms",
        "player_loader_ms",
        "consumer_read_ms",
        "history_read_ms",
        "decision_card_ms",
        "history_summary_ms",
    ):
        assert timing in source


def test_speed_v3_step1_profiler_restores_every_monkeypatch():
    assert PROFILER_PATH.exists(), "Step-1 PRA profiler module is missing"
    source = PROFILER_PATH.read_text(encoding="utf-8")
    assert "finally:" in source
    assert "performance.load_player_intelligence_same_session = original_loader" in source
    assert "player_intelligence._read_consumer = original_consumer" in source
    assert "player_intelligence._read_history = original_history" in source
    assert "player_intelligence._exact_pra_card = original_card" in source
    assert "player_intelligence._history_summary = original_summary" in source


def test_speed_v3_step1_router_wraps_frozen_step7_only():
    assert ROUTER_PATH.exists(), "Step-1 PRA profiler router is missing"
    source = ROUTER_PATH.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_wnba_nav_v2_step7 as frozen_step7" in source
    assert "original_render = final.render_step7_route" in source
    assert "profiler.render_profiled_step1_route(original_render)" in source
    assert "final.render_step7_route = original_render" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source


def test_app_activates_speed_v3_step1_and_keeps_step7_compatibility():
    source = APP_PATH.read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step1 import record_bootstrap_import_ms, render_app" in source
    assert "Frozen WNBA Navigation V2 Step 7 compatibility" in source

def test_speed_v3_step1_exposes_deployment_marker_before_page_gate():
    source = PROFILER_PATH.read_text(encoding="utf-8")
    assert 'data-wnba-pra-speed-v3-step1-deployed="true"' in source
    fn = source.split("def render_profiled_step1_route", 1)[1]
    assert "_render_deployment_marker(state)" in fn
    assert fn.index("_render_deployment_marker(state)") < fn.index("if state.page != navigation.PAGE_PLAYER")


def test_speed_v3_step1_public_proof_waits_for_deployment_before_timing():
    verifier = (ROOT / "devsystem" / "wnba_pra_speed_v3_step1_public_profile.py").read_text(encoding="utf-8")
    assert 'PROFILE_DEPLOYMENT_SELECTOR = \'[data-wnba-pra-speed-v3-step1-deployed="true"]\'' in verifier
    assert "def _wait_for_profiled_deployment(" in verifier
    run = verifier.split("def run(", 1)[1]
    assert "_wait_for_profiled_deployment(page)" in run
    assert run.index("_wait_for_profiled_deployment(page)") < run.index("game_started = time.monotonic()")



def test_step1_public_profiler_observes_navigation_without_reusing_step7_speed_gates():
    verifier = (ROOT / "devsystem" / "wnba_pra_speed_v3_step1_public_profile.py").read_text(encoding="utf-8")
    assert "PROFILE_GAME_SETUP_TIMEOUT_SECONDS = 120.0" in verifier
    assert "PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS = 120.0" in verifier
    assert 'frame, _ = _wait_page(page, "game", timeout_seconds=PROFILE_GAME_SETUP_TIMEOUT_SECONDS)' in verifier
    assert 'frame, _ = _wait_page(page, "player", timeout_seconds=PROFILE_PLAYER_OBSERVE_TIMEOUT_SECONDS)' in verifier
    assert "GAME_READY_BUDGET_SECONDS" not in verifier
    assert "PLAYER_READY_BUDGET_SECONDS" not in verifier
