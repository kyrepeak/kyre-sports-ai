from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.passing_yards_layered_hub_responsive_v1 import build_responsive_polish, RESPONSIVE_POLISH_CSS

css=build_responsive_polish()

assert 'data-py-step7-responsive-css="true"' in css
for bp in ("1024px","760px","430px"):
    assert f"max-width:{bp}" in RESPONSIVE_POLISH_CSS
for token in (
    "min-height:40px",
    "min-height:42px",
    "grid-template-columns:1fr",
    "overflow-wrap:anywhere",
    "overscroll-behavior-inline:contain",
    "max-width:100%",
):
    assert token in RESPONSIVE_POLISH_CSS

print("PASSING_YARDS_LAYERED_HUB_STEP7_RESPONSIVE_GREEN")
