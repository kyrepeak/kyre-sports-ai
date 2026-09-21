from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_game_total_theme_v1 import GAME_TOTAL_THEME_VERSION, build_game_total_theme_css

assert "BLACK + GLACIER BLUE" in GAME_TOTAL_THEME_VERSION
css = build_game_total_theme_css()

for marker in (
    'data-kyre-universal-theme="v1"',
    'data-kyre-universal-components-css="v1"',
    'data-kyre-universal-responsive="v1"',
    'data-kyre-game-total-universal="v1"',
):
    assert marker in css

for selector in (
    ".gt229-sportnav",
    ".gt233-category",
    ".gt225-hero",
    ".gt226-wrap",
    ".gt227-section",
    ".gt226-card",
    ".gt227-card",
):
    assert selector in css

for token in (
    "var(--kyre-glacier)",
    "var(--kyre-glacier-soft)",
    "var(--kyre-text-primary)",
    "var(--kyre-text-secondary)",
    "var(--kyre-surface)",
):
    assert token in css

page = Path("cfb_game_total_clean_page_v34.py").read_text()
assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v33"' in page
assert "PRESENTATION_ONLY = True" in page
assert "result = prior.render_game_total_hub(" in page
assert page.count("st.markdown(css, unsafe_allow_html=True)") == 2
assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page

router = Path("streamlit_memory_lazy_router_v190.py").read_text()
assert "import streamlit_memory_lazy_router_v181 as game_total_router" in router
assert "import streamlit_memory_lazy_router_v189 as prior" in router
assert 'GAME_TOTAL_PAGE = "cfb_game_total_clean_page_v34"' in router
assert "game_total_router.ACTIVE_PAGE = GAME_TOTAL_PAGE" in router
assert "game_total_router.ACTIVE_PAGE = original" in router

app = Path("app.py").read_text()
assert "from streamlit_memory_lazy_router_v190 import record_bootstrap_import_ms, render_app" in app
assert "activate_universal_shell()" in app
assert "CFB_GAME_TOTAL_UNIVERSAL_THEME_RUNTIME" in app
assert "MONEYLINE_UNIVERSAL_THEME_RUNTIME" in app

for path in ("cfb_game_total_clean_page_v33.py", "cfb_game_total_clean_page_v28.py"):
    assert Path(path).is_file()

for forbidden in (
    "requests.get(",
    "requests.post(",
    "projection =",
    "probability =",
    "_fit_calibration",
):
    assert forbidden not in page.lower()

print("SITEWIDE_THEME_ROLLOUT_STEP3_GAME_TOTAL_GREEN")
