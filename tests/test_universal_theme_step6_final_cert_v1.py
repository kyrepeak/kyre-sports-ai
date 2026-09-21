from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_universal_theme_v1 import THEME_VERSION, build_universal_theme_css
from kyre_universal_shell_v1 import SHELL_VERSION, build_universal_shell
from kyre_universal_components_v1 import COMPONENT_VERSION, build_component_showcase
from kyre_universal_responsive_v1 import RESPONSIVE_VERSION, build_responsive_css
import nfl_passing_yards_hub_v45 as v45

# Step 1 — theme foundation.
theme_css = build_universal_theme_css()
assert "BLACK + GLACIER BLUE" in THEME_VERSION
assert 'data-kyre-universal-theme="v1"' in theme_css
for token in (
    "--kyre-bg-0",
    "--kyre-glacier",
    "--kyre-glacier-strong",
    "--kyre-text-primary",
    "--kyre-text-secondary",
    "--kyre-success",
):
    assert token in theme_css

# Step 2 — universal shell.
assert "BLACK + GLACIER BLUE" in SHELL_VERSION
shell = build_universal_shell(
    '<div id="cert-content">CERTIFIED CONTENT</div>',
    active_nav="Passing Yards",
    slate_label="Certified Slate",
    sport_label="NFL",
)
for marker in (
    'data-kyre-universal-shell="v1"',
    'data-kyre-shell-sidebar="true"',
    'data-kyre-shell-topbar="true"',
    'data-kyre-shell-main="true"',
    'data-kyre-content-slot="true"',
):
    assert marker in shell
assert 'data-kyre-nav="Passing Yards" aria-current="page"' in shell

# Step 3 — shared components.
assert "BLACK + GLACIER BLUE" in COMPONENT_VERSION
showcase = build_component_showcase()
for marker in ("card", "button", "badge", "filter", "search", "stat", "accordion", "tab"):
    assert f'data-kyre-component="{marker}"' in showcase

# Step 5 — responsive overlay.
assert "DESKTOP + TABLET + MOBILE" in RESPONSIVE_VERSION
responsive = build_responsive_css()
assert 'data-kyre-universal-responsive="v1"' in responsive
for breakpoint in (
    "@media(min-width:1200px)",
    "@media(max-width:900px)",
    "@media(max-width:620px)",
    "@media(max-width:430px)",
):
    assert breakpoint in responsive
assert "min-height:44px" in responsive
assert "overflow-wrap:anywhere" in responsive

# Step 4 + 5 — final Passing Yards presentation chain.
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
passing = v45._responsive_player_cards_html(captured)
for marker in (
    'data-kyre-universal-theme="v1"',
    'data-kyre-universal-components-css="v1"',
    'data-passing-yards-universal="v44"',
    'data-kyre-universal-responsive="v1"',
):
    assert marker in passing
assert passing.count('data-universal-passing-qb=') == 2
assert "Monster Projection" in passing
assert "Market + Edge" in passing
assert "Open Full Breakdown" in passing
assert "LIVE DATA • MODEL FROZEN" in passing

# Frozen execution guardrails.
assert v45.FROZEN_PRIOR == "nfl_passing_yards_hub_v44"
assert v45.DISPLAY_ONLY is True
assert v45.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
assert v45.STAKE_SIZING_ENABLED is False

v45_source = Path("nfl_passing_yards_hub_v45.py").read_text().lower()
for forbidden in ("requests.get(", "requests.post(", "httpx.get(", "httpx.post("):
    assert forbidden not in v45_source
assert "prior._universal_player_cards_html" in v45_source
assert "prior.render_nfl_passing_yards_hub()" in v45_source

# Final router points to V45 and does not regress to V43/V44 as active owner.
router = Path("streamlit_memory_lazy_router_v188.py").read_text()
assert "import nfl_passing_yards_hub_v45 as passing_yards" in router
assert "nfl_passing_yards_hub_v44 as passing_yards" not in router
assert "nfl_passing_yards_hub_v43 as passing_yards" not in router

# The final chain must contain all rollout artifacts.
for path in (
    "kyre_universal_theme_v1.py",
    "kyre_universal_shell_v1.py",
    "kyre_universal_components_v1.py",
    "kyre_universal_responsive_v1.py",
    "nfl_passing_yards_hub_v44.py",
    "nfl_passing_yards_hub_v45.py",
):
    assert Path(path).is_file(), path

print("UNIVERSAL_THEME_STEP6_FINAL_CERT_GREEN")
