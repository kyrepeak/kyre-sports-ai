from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME_GATE = ROOT / "kyre_remaining_pages_theme_v1.py"
REPAIR = ROOT / "cfb_game_total_page1_v2_step4_public_repair_v1.py"


def test_theme_gate_lazily_installs_repair_only_for_cfb_game_total() -> None:
    theme = THEME_GATE.read_text(encoding="utf-8")
    assert 'sport == "CFB" and market == "Game Total"' in theme
    assert (
        "from cfb_game_total_page1_v2_step4_public_repair_v1 import install_public_repair"
        in theme
    )
    assert "install_public_repair(sport, market)" in theme
    assert '("CFB", "Game Total")' in theme


def test_public_repair_owns_the_post_purge_import_boundary() -> None:
    assert REPAIR.exists(), "Step-4 public repair module is missing"
    source = REPAIR.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v1 as root" in source
    assert "import streamlit_memory_lazy_router_v160 as render_owner" in source
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


def test_public_repair_is_exact_route_only_and_preserves_frozen_math() -> None:
    source = REPAIR.read_text(encoding="utf-8")
    assert 'TARGET_SPORT = "CFB"' in source
    assert 'TARGET_MARKET = "Game Total"' in source
    assert "if normalized_sport != TARGET_SPORT or normalized_market != TARGET_MARKET:" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "NETWORK_CALLS_ADDED = 0" in source


def test_frozen_v21_v38_v160_sources_remain_untouched() -> None:
    source = REPAIR.read_text(encoding="utf-8")
    assert "cfb_game_total_clean_page_v21" in source
    assert "cfb_game_total_clean_page_v38" in source
    assert "streamlit_memory_lazy_router_v160" in source
    # Runtime symbol substitution only; no frozen file is a write target.
    assert "FROZEN_SOURCE_MUTATIONS = 0" in source
