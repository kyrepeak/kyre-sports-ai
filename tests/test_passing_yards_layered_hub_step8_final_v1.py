from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards
from prototypes.passing_yards_layered_hub_tabs_v1 import build_layered_tabs
from prototypes.passing_yards_layered_hub_previews_v1 import build_hub_previews
from prototypes.passing_yards_layered_hub_responsive_v1 import build_responsive_polish

cards = [
    QBCard("Quarterback A","AAA","BBB","Away","Sun • 1:00 PM ET","Available"),
    QBCard("Quarterback B","CCC","DDD","Home","Sun • 4:25 PM ET","Available"),
]

content = (
    build_responsive_polish()
    + build_passing_yards_header()
    + build_layered_tabs()
    + build_qb_cards(cards)
    + build_hub_previews()
)
html = build_universal_shell(content)

# Frozen-layer coexistence
assert html.count('data-py-layered-shell="true"') == 1
assert html.count('data-py-step3-header="true"') == 1
assert html.count('data-py-step5-tabs="true"') == 1
assert html.count('data-py-step4-qb-section="true"') == 1
assert html.count('data-qb-card="true"') == 2
assert html.count('data-py-step6-preview-section="true"') == 1
assert html.count('data-py-step6-preview="') == 3
assert html.count('data-py-step7-responsive-css="true"') == 1

# Key UX contract
for label in ("Overview","Why","Matchup","Trends","Market","Deep Data"):
    assert f'data-py-layer-tab="{label}"' in html
for label in ("Why it matters","Trend snapshot","Market snapshot"):
    assert label in html
assert html.count("Open Full Breakdown →") == 3
assert "View QB →" in html
assert "Passing Yards" in html
assert "Quarterbacks" in html

# Responsive/mobile contract
for bp in ("max-width:1024px","max-width:760px","max-width:430px"):
    assert bp in html
assert "min-height:42px" in html
assert "overflow-wrap:anywhere" in html

# Standalone/prototype safety contract
source = Path("prototypes/passing_yards_layered_hub_app_final_v1.py").read_text()
assert "production" in source.lower()
assert "passing_yards_layered_hub_" in source
assert "pages/" not in source
assert "streamlit_app.py" not in source
assert "app.py" not in source

print("PASSING_YARDS_LAYERED_HUB_STEP8_FINAL_GREEN")
