from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_over_under_clean_page_v41.py"
LOADER = ROOT / "universal_runtime_v5_loader_v19.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_ou_v3.py"
APP = ROOT / "app.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v41_is_additive_over_frozen_v40_and_keeps_model_math_untouched() -> None:
    source = _source(PAGE)
    assert "import cfb_over_under_clean_page_v40 as frozen_page" in source
    assert 'FROZEN_PRESENTATION = "cfb_over_under_clean_page_v40"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "runtime_slate = frozen_page.runtime_slate" in source
    assert "final_model = frozen_page.final_model" in source


def test_v41_line_lab_is_a_real_half_point_slider_with_precision_controls() -> None:
    source = _source(PAGE)
    assert 'st.slider(' in source
    assert '"🎚️ Line Lab total"' in source
    assert "step=0.5" in source
    assert "min_value=20.0" in source
    assert "max_value=100.0" in source
    assert "on_click=_nudge_line" in source
    assert '"−0.5"' in source
    assert '"+0.5"' in source
    assert 'st.number_input("🎚️ Line Lab total"' not in source
    assert "runtime_slate.analyze_game(selected_game, day, float(line))" in source


def test_v41_has_readable_typography_and_compact_matchup_hero() -> None:
    source = _source(PAGE)
    assert ".ou41-heading{color:#f4f8fb;font-size:1.28rem" in source
    assert ".ou41-sub{color:#a8bac7;font-size:.92rem" in source
    assert ".ou41-card b{display:block;color:#eef5f8;font-size:1.02rem" in source
    assert ".ou41-matchup-logo img{width:72px;height:72px" in source
    assert "def _compact_matchup_html(" in source
    assert "_hero_html(" not in source


def test_v41_emphasizes_pick_and_plain_english_scan_sections() -> None:
    source = _source(PAGE)
    assert ".ou41-pick strong{display:block;color:#fff;font-size:2rem" in source
    assert "MODEL PICK" in source
    assert "WHY THE MODEL LIKES IT" in source
    assert "EVIDENCE READY" in source
    assert "WHAT MOVES THE TOTAL" in source
    assert "def _driver_signal(" in source
    assert "→ CONTEXT" in source
    assert "↑ OVER" in source
    assert "↓ UNDER" in source


def test_v41_keeps_engineering_copy_in_collapsed_diagnostics() -> None:
    source = _source(PAGE)
    assert 'with st.expander("🛠 DIAGNOSTICS", expanded=False):' in source
    assert "MODEL_VERSION" in source
    assert "Projection mutation" in source
    assert "SPORTSBOOK INFLUENCE 0.0%" not in source
    assert "EXACT LOGOS PRESERVED" not in source


def test_loader_v19_routes_only_cfb_over_under_to_v41() -> None:
    source = _source(LOADER)
    assert "import universal_runtime_v5_loader_v18 as prior" in source
    assert 'route.sport_id == "cfb" and route.market_id == "over-under"' in source
    assert 'importlib.import_module("cfb_over_under_clean_page_v41")' in source
    assert "return base.renderer(page)" in source
    assert "return prior.resolve_destination(route)" in source


def test_terminal_v3_and_app_advance_only_the_loader_handoff() -> None:
    source = _source(TERMINAL)
    assert "import streamlit_memory_lazy_router_universal_runtime_v5 as prior" in source
    assert "from universal_runtime_v5_loader_v19 import choose_prefetch, load_destination, resolve_destination" in source
    assert "prior.choose_prefetch = choose_prefetch" in source
    assert "prior.load_destination = load_destination" in source
    assert "prior.resolve_destination = resolve_destination" in source
    assert "return prior.render_app()" in source
    app_source = _source(APP)
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_ou_v3" in app_source
