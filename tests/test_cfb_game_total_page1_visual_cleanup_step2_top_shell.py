from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "cfb_game_total_page1_visual_cleanup_step2_top_shell_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_visual_cleanup_step2.py"
APP = ROOT / "app.py"


def _load_helper():
    assert HELPER.is_file(), "Step-2 top-shell helper must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_visual_cleanup_step2", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step2_runtime_artifacts_exist_before_green() -> None:
    assert HELPER.is_file(), "Step-2 top-shell helper must exist before GREEN"
    assert ROUTER.is_file(), "Step-2 additive router must exist before GREEN"


def test_step2_top_shell_is_dynamic_phoenix_summary_first() -> None:
    helper = _load_helper()
    identity = {
        "away": {"team": "Arizona", "conference": "big-12"},
        "home": {"team": "Utah", "conference": "big-12"},
        "venue": "Rice-Eccles Stadium",
    }
    away = {"team": "Arizona", "record": "5-1"}
    home = {"team": "Utah", "record": "4-2"}
    game = {
        "kickoff_iso": "2026-10-10T23:30:00Z",
        "game_date": "2026-10-10",
        "venue_location": "Salt Lake City, UT",
        "temperature": "68",
        "precipitation_pct": "10",
        "weather": "Clear",
        "wind": "6 mph",
    }

    html = helper.build_top_shell_html(
        identity,
        away,
        home,
        game,
        away_logo_html="<img alt='Arizona'>",
        home_logo_html="<img alt='Utah'>",
    )

    for expected in (
        'data-testid="gtvc2-matchup-hero"',
        'data-testid="gtvc2-context-strip"',
        'data-testid="gtvc2-view-tabs"',
        "Arizona",
        "Utah",
        "5-1",
        "4-2",
        "Rice-Eccles Stadium",
        "Salt Lake City, UT",
        "68°",
        "10% precipitation",
        "Clear",
        "6 mph",
        "4:30 PM AZ",
        "Overview",
        "Full Analysis",
    ):
        assert expected in html

    source = HELPER.read_text(encoding="utf-8")
    assert "Ohio State" not in source
    assert "Oregon" not in source
    assert helper.PHOENIX_TZ == "America/Phoenix"
    assert helper.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert helper.MAY_MODIFY_PROJECTION is False
    assert helper.MAY_MODIFY_MARKET_OWNERSHIP is False


def test_step2_router_is_exact_route_overlay_and_app_activation_is_additive() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")

    assert "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration as prior" in router
    assert "streamlit_memory_lazy_router_v181 as route_owner" in router
    assert "cfb_game_total_page1_step3_presentation_v1 as presentation" in router
    assert "if not route_owner._game_total_route_active():" in router
    assert "return prior.render_app()" in router
    assert "presentation.build_matchup_hero_html = build_top_shell_html" in router
    assert "presentation.build_matchup_hero_html = original" in router
    assert "MAY_MODIFY_OTHER_SPORTS = False" in router
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router

    assert (
        "from streamlit_memory_lazy_router_cfb_game_total_visual_cleanup_step2 "
        "import record_bootstrap_import_ms, render_app"
    ) in app
    assert "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_STEP2_TOP_SHELL_2026_10_09" in app


def test_step2_preserves_step1_and_prior_runtime_owners() -> None:
    helper = _load_helper()
    assert helper.STEP1_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP1_TARGET_LOCK_FROZEN"
    assert helper.PRESERVE_DYNAMIC_SELECTED_GAME_DATA is True
    assert helper.OVERVIEW_LABEL == "Overview"
    assert helper.FULL_ANALYSIS_LABEL == "Full Analysis"
