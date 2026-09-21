from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_universal_components_v1 import (
    COMPONENT_VERSION,
    FOUNDATION_VERSION,
    build_accordion,
    build_badge,
    build_button,
    build_card,
    build_component_showcase,
    build_components_css,
    build_filter_control,
    build_search_control,
    build_stat_tile,
    build_tabs,
)
from kyre_universal_shell_v1 import build_universal_shell
from kyre_universal_theme_v1 import THEME_VERSION

assert "BLACK + GLACIER BLUE" in COMPONENT_VERSION
assert FOUNDATION_VERSION == THEME_VERSION

css = build_components_css()
assert 'data-kyre-universal-components-css="v1"' in css
for token in (
    "var(--kyre-glacier)",
    "var(--kyre-glacier-soft)",
    "var(--kyre-text-primary)",
    "var(--kyre-text-secondary)",
    "var(--kyre-text-muted)",
    "var(--kyre-radius-xl)",
    "var(--kyre-shadow-card)",
):
    assert token in css
assert "@media(max-width:900px)" in css
assert "@media(max-width:620px)" in css

assert 'data-kyre-component="card"' in build_card("Card", "Body", eyebrow="Test")
assert 'data-kyre-component="button"' in build_button("Go")
assert 'data-kyre-component="badge"' in build_badge("Live", tone="success")
assert 'data-kyre-component="filter"' in build_filter_control("Team", "All")
assert 'data-kyre-component="search"' in build_search_control()
assert 'data-kyre-component="stat"' in build_stat_tile("Projection", "287.4", meta="Model")
assert 'data-kyre-component="accordion"' in build_accordion("Details", "Body")

tabs = build_tabs(("Overview", "Trends", "Market"), active="Trends")
assert tabs.count('data-kyre-component="tab"') == 3
assert tabs.count('aria-selected="true"') == 1
assert '>Trends<' in tabs

showcase = build_component_showcase()
for marker in ("card", "button", "badge", "filter", "search", "stat", "accordion", "tab"):
    assert f'data-kyre-component="{marker}"' in showcase
assert 'data-kyre-component-showcase="v1"' in showcase

wrapped = build_universal_shell(showcase, active_nav="Passing Yards")
assert 'data-kyre-universal-theme="v1"' in wrapped
assert 'data-kyre-universal-shell="v1"' in wrapped
assert 'data-kyre-component-showcase="v1"' in wrapped

source = Path("kyre_universal_components_v1.py").read_text()
for forbidden in ("streamlit_memory_lazy_router", "render_nfl_passing_yards_hub", "app.py"):
    assert forbidden not in source

print("UNIVERSAL_THEME_STEP3_COMPONENTS_GREEN")
