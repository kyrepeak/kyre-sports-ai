from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards
from prototypes.passing_yards_layered_hub_tabs_v1 import build_layered_tabs, TABS, TABS_CSS

cards=[QBCard("Quarterback A","AAA","BBB","Away","Sun • 1:00 PM ET")]
html=build_universal_shell(build_passing_yards_header()+build_layered_tabs()+build_qb_cards(cards))

assert 'data-py-step5-tabs="true"' in html
assert 'role="tablist"' in html
assert html.count('role="tab"') == 6
assert html.count('aria-selected="true"') == 1
for label, anchor in TABS:
    assert f'data-py-layer-tab="{label}"' in html
    assert f'href="#{anchor}"' in html
assert 'Overview' in html and 'Why' in html and 'Matchup' in html
assert 'Trends' in html and 'Market' in html and 'Deep Data' in html
assert '@media (max-width:760px)' in TABS_CSS
assert 'overflow-x:auto' in TABS_CSS
assert 'data-py-step6-preview=' not in html
assert 'Open Full Breakdown' not in html

print("PASSING_YARDS_LAYERED_HUB_STEP5_TABS_GREEN")
