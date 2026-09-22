from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_remaining_pages_theme_v1 import (
    EXCLUDED_FROZEN_ROUTES,
    REMAINING_PAGES_CONTAINER_CLASS,
    REMAINING_PAGES_CONTAINER_KEY,
    REMAINING_PAGES_THEME_VERSION,
    build_remaining_pages_theme_css,
    should_theme_route,
)

assert "BLACK + GLACIER BLUE" in REMAINING_PAGES_THEME_VERSION
assert REMAINING_PAGES_CONTAINER_KEY == "kyre_universal_remaining_pages"
assert REMAINING_PAGES_CONTAINER_CLASS == "st-key-kyre_universal_remaining_pages"

assert EXCLUDED_FROZEN_ROUTES == {
    ("NFL", "Passing Yards"),
    ("NFL", "Moneyline"),
    ("CFB", "Game Total"),
}
for route in EXCLUDED_FROZEN_ROUTES:
    assert should_theme_route(*route) is False

for route in (
    ("NFL", "Slate"),
    ("NFL", "Spread"),
    ("NFL", "Game Total"),
    ("NFL", "Rushing Yards"),
    ("NFL", "Receiving Yards"),
    ("NFL", "Daily Picks"),
    ("CFB", "Moneyline"),
    ("CFB", "Over/Under"),
    ("MLB", "Slate"),
    ("MLB", "Moneyline"),
    ("MLB", "Game Total"),
    ("WNBA", "Points"),
    ("WNBA", "Moneyline"),
    ("WNBA", "Game Total"),
):
    assert should_theme_route(*route) is True, route

css = build_remaining_pages_theme_css()
for marker in (
    'data-kyre-universal-theme="v1"',
    'data-kyre-universal-components-css="v1"',
    'data-kyre-universal-responsive="v1"',
    'data-kyre-remaining-pages-theme="v1"',
):
    assert marker in css

for selector in (
    '[data-testid="stMetric"]',
    '.stButton button',
    '[data-baseweb="select"]>div',
    '[data-testid="stExpander"]',
    '[data-testid="stDataFrame"]',
    '[data-testid="stAlert"]',
    '[data-baseweb="tab-list"]',
    '[class*="card"]',
    '[class*="panel"]',
):
    assert selector in css

router = Path("streamlit_memory_lazy_router_v191.py").read_text()
assert "import streamlit_memory_lazy_router_v190 as prior" in router
assert "should_theme_route(sport, market)" in router
assert "st.container(key=REMAINING_PAGES_CONTAINER_KEY)" in router
assert "return prior.render_app()" in router
assert "PRESENTATION_ONLY = True" in router
assert "MAY_MODIFY_PROJECTION = False" in router

app = Path("app.py").read_text()
assert "from streamlit_memory_lazy_router_v191 import record_bootstrap_import_ms, render_app" in app
assert "activate_universal_shell()" in app
assert "REMAINING_PAGES_UNIVERSAL_THEME_RUNTIME" in app
assert "MONEYLINE_UNIVERSAL_THEME_RUNTIME" in app
assert "CFB_GAME_TOTAL_UNIVERSAL_THEME_RUNTIME" in app

# Active market contracts remain present and unchanged in their frozen owners.
root = Path("streamlit_memory_lazy_router_v1.py").read_text()
for market in (
    '"Slate"', '"Moneyline"', '"Spread"', '"Game Total"', '"Passing Yards"',
    '"Rushing Yards"', '"Receiving Yards"', '"Daily Picks"',
    '"Points"', '"Rebounds"', '"Assists"', '"Run Line"', '"Live Game"',
):
    assert market in root
cfb = Path("cfb_hub_v1.py").read_text()
for market in ('"Moneyline"', '"Over/Under"', '"Game Total"'):
    assert market in cfb

for forbidden in (
    "requests.get(",
    "requests.post(",
    "_build_game_output(",
    "_fit_calibration_model(",
):
    assert forbidden not in router.lower()

print("SITEWIDE_THEME_ROLLOUT_STEP4_REMAINING_PAGES_GREEN")
