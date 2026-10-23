from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1.py"


def test_production_entrypoint_activates_loading_progress_terminal() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1" in source
    assert '_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-universal-loading-progress-v1-activation-r1-20261022"' in source


def test_activation_terminal_remains_thin_and_inherits_current_route_owner() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1 as prior" in source
    assert "resolve_destination = prior.resolve_destination" in source
    assert "record_bootstrap_import_ms = prior.record_bootstrap_import_ms" in source
    assert "render_page_experience_app_v4" in source
