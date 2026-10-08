from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_v191.py"
REPAIR = ROOT / "cfb_game_total_page1_v2_step4_public_repair_v1.py"


def test_v191_installs_public_repair_before_delegating() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    assert (
        "from cfb_game_total_page1_v2_step4_public_repair_v1 import install_public_repair"
        in router
    )
    assert "install_public_repair()" in router
    assert router.index("install_public_repair()") < router.index("sport, market = _active_route()")
    assert "return prior.render_app()" in router


def test_v191_preserves_remaining_pages_theme_contract() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v190 as prior" in router
    assert "should_theme_route(sport, market)" in router
    assert "st.container(key=REMAINING_PAGES_CONTAINER_KEY)" in router
    assert "PRESENTATION_ONLY = True" in router
    assert "MAY_MODIFY_PROJECTION = False" in router
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router


def test_public_repair_owns_the_post_purge_import_boundary() -> None:
    assert REPAIR.exists(), "Step-4 public repair module is missing"
    source = REPAIR.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v1 as root" in source
    assert "import streamlit_memory_lazy_router_v160 as render_owner" in source
    assert "import streamlit_memory_lazy_router_v181 as route_owner" in source
    assert 'TARGET_PAGE = "cfb_game_total_clean_page_v38"' in source
    assert 'LATE_OWNER = "cfb_game_total_clean_page_v21"' in source
    assert "original_import = root._import" in source
    assert "root._import = import_with_step4_repair" in source
    assert "root._import = original_import" in source
    assert "late_owner = importlib.import_module(LATE_OWNER)" in source
    assert (
        "late_owner._game_total_hero_html_v21 = page._step4_prediction_market_html_v38"
        in source
    )


def test_public_repair_wraps_v160_exact_surface_idempotently() -> None:
    source = REPAIR.read_text(encoding="utf-8")
    assert "render_owner._render_exact_game_total_surface" in source
    assert "_cfb_step4_public_repair_installed" in source
    assert "setattr(repaired_render_exact_game_total_surface" in source
    assert "render_owner._render_exact_game_total_surface = repaired_render_exact_game_total_surface" in source


def test_public_repair_uses_authoritative_route_predicate_and_preserves_math() -> None:
    source = REPAIR.read_text(encoding="utf-8")
    assert "if not route_owner._game_total_route_active():" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "FROZEN_SOURCE_MUTATIONS = 0" in source


def test_repair_does_not_change_frozen_source_files() -> None:
    source = REPAIR.read_text(encoding="utf-8")
    assert "cfb_game_total_clean_page_v21" in source
    assert "cfb_game_total_clean_page_v38" in source
    assert "streamlit_memory_lazy_router_v160" in source
    assert "Runtime symbol substitution only" in source
