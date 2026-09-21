from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nfl_passing_yards_hub_v44 as v44

assert v44.FROZEN_PRIOR == "nfl_passing_yards_hub_v43"
assert v44.DISPLAY_ONLY is True
assert v44.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
assert v44.STAKE_SIZING_ENABLED is False

captured = {
    "identity": ["QB ONE", "QB TWO"],
    "projection": ["PROJ ONE", "PROJ TWO"],
    "market": ["MARKET ONE", "MARKET TWO"],
    "profile": ["PROFILE ONE", "PROFILE TWO"],
    "defense": ["DEF ONE", "DEF TWO"],
    "pressure": ["PRESS ONE", "PRESS TWO"],
    "personnel": ["PERSONNEL ONE", "PERSONNEL TWO"],
    "environment": ["ENVIRONMENT"],
    "context": ["CONTEXT ONE", "CONTEXT TWO"],
    "distribution": ["DIST ONE", "DIST TWO"],
}
html = v44._universal_player_cards_html(captured)

assert 'data-passing-yards-universal="v44"' in html
assert 'data-kyre-universal-theme="v1"' in html
assert 'data-kyre-universal-components-css="v1"' in html
assert "--kyre-glacier:" in html
assert "var(--kyre-glacier)" in html
assert "Passing Yards" in html
assert "Monster Projection" in html
assert "Market + Edge" in html
assert "Open Full Breakdown" in html
assert "LIVE DATA • MODEL FROZEN" in html
assert html.count('data-universal-passing-qb=') == 2
for value in ("QB ONE", "QB TWO", "PROJ ONE", "MARKET TWO", "ENVIRONMENT"):
    assert value in html

source = Path("nfl_passing_yards_hub_v44.py").read_text()
for forbidden in (
    "requests.get(",
    "projection = ",
    "probability = ",
    "sportsbook_projection_influence = 1",
):
    assert forbidden not in source.lower()

router = Path("streamlit_memory_lazy_router_v188.py").read_text()
assert "nfl_passing_yards_hub_v44" in router
assert "nfl_passing_yards_hub_v43 as passing_yards" not in router

print("UNIVERSAL_THEME_STEP4_PASSING_YARDS_GREEN")
