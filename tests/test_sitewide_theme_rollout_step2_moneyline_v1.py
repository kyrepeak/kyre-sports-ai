from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_moneyline_theme_v1 import MONEYLINE_THEME_VERSION, build_moneyline_theme_css

assert "BLACK + GLACIER BLUE" in MONEYLINE_THEME_VERSION

css = build_moneyline_theme_css("<style>.frozen-v9-proof{display:block}</style>")
for marker in (
    'data-kyre-universal-theme="v1"',
    'data-kyre-universal-components-css="v1"',
    'data-kyre-universal-responsive="v1"',
    'data-kyre-moneyline-universal="v1"',
):
    assert marker in css
assert ".frozen-v9-proof" in css
for selector in (
    ".kml9-hero",
    ".kml9-matchup-card",
    ".kml9-team-panel",
    ".kml9-stat.hero",
    ".kml9-verdict",
):
    assert selector in css
for token in (
    "var(--kyre-bg-1)",
    "var(--kyre-glacier)",
    "var(--kyre-glacier-soft)",
    "var(--kyre-text-primary)",
    "var(--kyre-text-secondary)",
    "var(--kyre-text-muted)",
):
    assert token in css

v13 = Path("nfl_moneyline_hub_v13.py").read_text()
assert 'FROZEN_PRIOR = "nfl_moneyline_hub_v12"' in v13
assert 'FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"' in v13
assert "presentation._CSS = build_moneyline_theme_css(original_css)" in v13
assert "return prior.render_nfl_hub(market)" in v13
assert "presentation._CSS = original_css" in v13
assert "SPORTSBOOK_MODEL_INFLUENCE = 0.0" in v13
assert "MONTE_CARLO_SIMULATIONS = 5_000_000" in v13

for forbidden in (
    "requests.get(",
    "requests.post(",
    "_build_game_output(",
    "_fit_calibration_model(",
    "fetch_nfl_moneyline_markets(",
):
    assert forbidden not in v13

router = Path("streamlit_memory_lazy_router_v189.py").read_text()
assert "import streamlit_memory_lazy_router_v188 as prior" in router
assert 'MONEYLINE_HUB = "nfl_moneyline_hub_v13"' in router
assert "moneyline_router.ACTIVE_MONEYLINE_HUB = MONEYLINE_HUB" in router
assert "return prior.render_app()" in router

app = Path("app.py").read_text()
assert "from streamlit_memory_lazy_router_v189 import record_bootstrap_import_ms, render_app" in app
assert "activate_universal_shell()" in app
assert "MONEYLINE_UNIVERSAL_THEME_RUNTIME" in app

print("SITEWIDE_THEME_ROLLOUT_STEP2_MONEYLINE_GREEN")
