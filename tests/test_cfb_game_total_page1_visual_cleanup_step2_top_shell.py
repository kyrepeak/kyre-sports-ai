from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "cfb_game_total_page1_visual_cleanup_step2_top_shell_v1.py"
ACTIVATION = ROOT / "cfb_game_total_page1_visual_cleanup_step2_activation_v1.py"
THEME = ROOT / "kyre_game_total_theme_v1.py"
FROZEN_SHELL = ROOT / "kyre_universal_shell_runtime_v1.py"


def _load_helper():
    assert HELPER.is_file(), "Step-2 top-shell helper must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_visual_cleanup_step2", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step2_runtime_artifacts_exist_before_green() -> None:
    assert HELPER.is_file(), "Step-2 top-shell helper must exist before GREEN"
    assert ACTIVATION.is_file(), "Step-2 activation must exist before GREEN"
    assert THEME.is_file(), "CFB-only unfrozen theme seam must exist before GREEN"


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


def test_step2_activation_uses_unfrozen_cfb_theme_seam() -> None:
    activation = ACTIVATION.read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    frozen_shell = FROZEN_SHELL.read_text(encoding="utf-8")

    assert 'PRESENTATION_MODULE = "cfb_game_total_page1_step3_presentation_v1"' in activation
    assert "presentation = importlib.import_module(PRESENTATION_MODULE)" in activation
    assert "presentation.build_matchup_hero_html = build_top_shell_html" in activation
    assert "MAY_MODIFY_OTHER_SPORTS = False" in activation
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in activation
    assert "FROZEN_SOURCE_MUTATIONS = 0" in activation

    # Step 2 must no longer depend on the purged/frozen router or frozen shell.
    for forbidden in (
        "streamlit_memory_lazy_router_v1 as root",
        "streamlit_memory_lazy_router_v160 as render_owner",
        "streamlit_memory_lazy_router_v181 as route_owner",
        "root._import",
    ):
        assert forbidden not in activation

    assert (
        "from cfb_game_total_page1_visual_cleanup_step2_activation_v1 import "
        "install_step2_top_shell"
    ) in theme
    assert "install_step2_top_shell()" in theme
    assert theme.index("install_step2_top_shell()") < theme.index("return (")

    # Frozen universal shell is restored and must not own Step 2.
    assert "cfb_game_total_page1_visual_cleanup_step2_activation_v1" not in frozen_shell
    assert "install_step2_top_shell()" not in frozen_shell


def test_step2_preserves_step1_and_prior_runtime_owners() -> None:
    helper = _load_helper()
    assert helper.STEP1_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP1_TARGET_LOCK_FROZEN"
    assert helper.PRESERVE_DYNAMIC_SELECTED_GAME_DATA is True
    assert helper.OVERVIEW_LABEL == "Overview"
    assert helper.FULL_ANALYSIS_LABEL == "Full Analysis"

    # Frozen/current owners must remain present and are dependencies only.
    for path in (
        "cfb_game_total_clean_page_v38.py",
        "cfb_game_total_clean_page_v36.py",
        "cfb_game_total_page1_step3_presentation_v1.py",
        "cfb_game_total_page1_v2_step4_public_repair_v1.py",
        "streamlit_memory_lazy_router_v160.py",
        "streamlit_memory_lazy_router_v181.py",
        "streamlit_memory_lazy_router_v190.py",
        "streamlit_memory_lazy_router_v191.py",
        "kyre_universal_shell_runtime_v1.py",
    ):
        assert (ROOT / path).is_file()
