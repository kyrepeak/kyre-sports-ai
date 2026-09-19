from __future__ import annotations

from pathlib import Path


ROUTER = Path("streamlit_memory_lazy_router_v165.py")
APP = Path("app.py")


def test_v165_uses_stable_v162_runtime_delegate_and_page_v19():
    source = ROUTER.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v162 as prior" in source
    assert "import streamlit_memory_lazy_router_v163 as prior" not in source
    assert "import streamlit_memory_lazy_router_v164 as prior" not in source
    assert 'SAFE_RUNTIME_DELEGATE = "streamlit_memory_lazy_router_v162"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v164"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v19"' in source
    assert "return prior._render_exact_game_total_surface()" in source
    assert "return prior.render_app()" in source


def test_v165_owns_step6_cert_route_without_v163_cert_attribute_dependency():
    source = ROUTER.read_text(encoding="utf-8")
    assert 'STEP6_CERT_QUERY_KEY = "ks_cfb_step6_cert"' in source
    assert "def _step6_cert_requested" in source
    assert "def _render_step6_cert_surface" in source
    assert "st.query_params.get(STEP6_CERT_QUERY_KEY)" in source
    assert 'data-testid="cfb-game-total-v185-step6-cert-heartbeat"' in source
    assert "page = importlib.import_module(ACTIVE_PAGE)" in source
    assert "page.render_step6_cert_surface()" in source
    assert "prior.STEP6_CERT_QUERY_KEY" not in source
    assert "prior.STEP6_CERT_ROUTER_MARKER" not in source


def test_v165_heartbeat_proves_v184_v185_and_production_hotfix_identity():
    source = ROUTER.read_text(encoding="utf-8")
    assert "CFB_GAME_TOTAL_V184_STEP6_SCORING_CREATION_ACTIVE" in source
    assert "CFB_GAME_TOTAL_V185_STEP6_VISUAL_PARITY_ACTIVE" in source
    assert "CFB_GAME_TOTAL_V185_ROUTER_V165_PRODUCTION_HOTFIX_ACTIVE" in source
    assert "CFB_GAME_TOTAL_V185_STEP6_VISUAL_PARITY_ROUTER_ACTIVE" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_app_runtime_boots_v165_and_retains_v164_v163_source_compatibility():
    source = APP.read_text(encoding="utf-8")
    runtime = source[source.find("try:"):]
    assert "from streamlit_memory_lazy_router_v165 import record_bootstrap_import_ms, render_app" in runtime
    assert "from streamlit_memory_lazy_router_v164 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v163 import record_bootstrap_import_ms, render_app" in source
