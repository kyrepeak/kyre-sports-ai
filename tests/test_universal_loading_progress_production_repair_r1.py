from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
RUNTIME = ROOT / "universal_page_experience_runtime_v5.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_repair_r1.py"


def test_server_loader_stays_authoritative_until_destination_commit() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    load_pos = source.index("loaded = core.load_destination(adapter)")
    render_pos = source.index("adapter.renderer(loaded)")
    clear_pos = source.index("transition_slot.empty()")
    assert load_pos < render_pos < clear_pos


def test_client_component_mount_never_controls_server_loader_lifetime() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    assert "if is_transition and client_controller:" not in source
    assert "_mount_page_experience_controller_v5(runtime.active)" in source
    assert "_server_progress(transition_slot, runtime.active, 35, \"Loading page module\")" in source


def test_first_post_deploy_route_change_is_detected_without_new_session_key() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    assert 'LAST_RENDERED_ROUTE_KEY = "ks_universal_page_experience_last_rendered_route_v4"' in source
    assert "before_identity = route_identity(before_runtime.active)" in source
    assert "is_transition = before_identity != identity" in source


def test_truthful_progress_stages_remain_server_rendered() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    for percent, label in (
        (15, "Routing page"),
        (35, "Loading page module"),
        (70, "Loading intelligence"),
        (90, "Preparing page"),
        (100, "Ready"),
    ):
        assert f'_server_progress(transition_slot, runtime.active, {percent}, "{label}")' in source


def test_terminal_uses_server_authoritative_runtime_successor() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1 as prior" in source
    assert "from universal_page_experience_runtime_v5 import render_page_experience_app_v5" in source
    assert "return render_page_experience_app_v5(frozen_runtime)" in source


def test_production_entrypoint_activates_repaired_terminal() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_repair_r1" in source
    assert '_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-universal-loading-progress-v1-production-repair-r1-20261022"' in source
