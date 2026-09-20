from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards
from prototypes.passing_yards_layered_hub_tabs_v1 import build_layered_tabs
from prototypes.passing_yards_layered_hub_previews_v1 import build_hub_previews, default_previews, PREVIEW_CSS

cards=[QBCard("Quarterback A","AAA","BBB","Away","Sun • 1:00 PM ET")]
html=build_universal_shell(
    build_passing_yards_header()
    + build_layered_tabs()
    + build_qb_cards(cards)
    + build_hub_previews()
)

assert 'data-py-step6-preview-section="true"' in html
assert html.count('data-py-step6-preview="') == 3
for kind in ("why","trends","market"):
    assert f'data-py-step6-preview="{kind}"' in html
    assert f'id="py-{kind}"' in html
    assert f'href="#full-{kind}"' in html
assert html.count("Open Full Breakdown →") == 3
assert "Why it matters" in html
assert "Trend snapshot" in html
assert "Market snapshot" in html
assert "Scan here • open deeper only when needed" in html
assert '@media (max-width:900px)' in PREVIEW_CSS
assert '@media (max-width:520px)' in PREVIEW_CSS
assert len(default_previews()) == 3
assert 'data-deep-data-table=' not in html
assert 'data-full-breakdown-panel=' not in html

print("PASSING_YARDS_LAYERED_HUB_STEP6_PREVIEWS_GREEN")
