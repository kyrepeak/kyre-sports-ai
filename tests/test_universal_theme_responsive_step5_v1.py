from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_universal_responsive_v1 import RESPONSIVE_VERSION, build_responsive_css
import nfl_passing_yards_hub_v45 as v45

assert "DESKTOP + TABLET + MOBILE" in RESPONSIVE_VERSION
css = build_responsive_css()

assert 'data-kyre-universal-responsive="v1"' in css
for breakpoint in (
    "@media(min-width:1200px)",
    "@media(max-width:1100px)",
    "@media(max-width:900px)",
    "@media(max-width:780px)",
    "@media(max-width:620px)",
    "@media(max-width:430px)",
    "@media(max-width:360px)",
):
    assert breakpoint in css

for rule in (
    "max-width:100%",
    "overflow-wrap:anywhere",
    "min-height:44px",
    "grid-template-columns:1fr",
    "flex-wrap:wrap",
    "overflow-x:auto",
):
    assert rule in css

assert ".kyre-universe-topbar" in css
assert ".kyre-universe-search" in css
assert ".kyre-ui-tab" in css
assert ".kyre-ui-accordion summary" in css
assert ".ks-v44-result" in css
assert ".ks-v44-previews" in css

captured = {
    "identity": ["QB ONE", "QB TWO"],
    "projection": ["PROJ ONE", "PROJ TWO"],
    "market": ["MARKET ONE", "MARKET TWO"],
    "profile": ["PROFILE ONE", "PROFILE TWO"],
    "defense": ["DEF ONE", "DEF TWO"],
    "pressure": ["PRESS ONE", "PRESS TWO"],
    "personnel": ["PERSONNEL ONE", "PERSONNEL TWO"],
    "environment": ["ENV"],
    "context": ["CTX ONE", "CTX TWO"],
    "distribution": ["DIST ONE", "DIST TWO"],
}
html = v45._responsive_player_cards_html(captured)
assert 'data-kyre-universal-responsive="v1"' in html
assert 'data-passing-yards-universal="v44"' in html
assert 'data-kyre-universal-theme="v1"' in html
assert 'data-kyre-universal-components-css="v1"' in html
assert "QB ONE" in html and "QB TWO" in html

assert v45.FROZEN_PRIOR == "nfl_passing_yards_hub_v44"
assert v45.DISPLAY_ONLY is True
assert v45.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
assert v45.STAKE_SIZING_ENABLED is False

source = Path("nfl_passing_yards_hub_v45.py").read_text().lower()
for forbidden in ("requests.get(", "requests.post(", "httpx.get(", "httpx.post("):
    assert forbidden not in source
assert "prior._universal_player_cards_html" in source
assert "prior.render_nfl_passing_yards_hub()" in source

router = Path("streamlit_memory_lazy_router_v188.py").read_text()
assert "nfl_passing_yards_hub_v45" in router
assert "nfl_passing_yards_hub_v44 as passing_yards" not in router

print("UNIVERSAL_THEME_STEP5_RESPONSIVE_GREEN")
