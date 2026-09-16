from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_real_app_boots_v152_router() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v152 import record_bootstrap_import_ms, render_app" in app_source


def test_v152_router_exposes_production_heartbeat() -> None:
    router = ROOT / "streamlit_memory_lazy_router_v152.py"
    assert router.exists(), "V152 router does not exist yet"
    source = router.read_text(encoding="utf-8")
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"' in source
    assert "return prior.render_app()" in source


def test_v152_activation_keeps_sportsbook_and_model_frozen() -> None:
    router = ROOT / "streamlit_memory_lazy_router_v152.py"
    assert router.exists(), "V152 router does not exist yet"
    source = router.read_text(encoding="utf-8")
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
