from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards, QB_CARDS_CSS

cards = [
    QBCard("Quarterback A", "AAA", "BBB", "Away", "Sun • 1:00 PM ET", "Available"),
    QBCard("Quarterback B", "CCC", "DDD", "Home", "Sun • 4:25 PM ET", "Questionable"),
]
html = build_universal_shell(build_passing_yards_header() + build_qb_cards(cards))

assert 'data-py-layered-shell="true"' in html
assert 'data-py-step3-header="true"' in html
assert 'data-py-step4-qb-section="true"' in html
assert html.count('data-qb-card="true"') == 2
assert html.count('data-qb-identity="true"') == 2
assert html.count('data-qb-matchup="true"') == 2
assert html.count('data-qb-status="true"') == 2
for token in ("Quarterback A", "AAA vs BBB", "AWAY", "Quarterback B", "CCC vs DDD", "HOME"):
    assert token in html
assert 'View QB →' in html
assert 'aria-label="Open Quarterback A details"' in html
assert '@media (max-width:760px)' in QB_CARDS_CSS
assert '@media (max-width:420px)' in QB_CARDS_CSS
assert 'data-qb-stat-tile=' not in html
assert 'Projection' not in build_qb_cards(cards)

print("PASSING_YARDS_LAYERED_HUB_STEP4_QB_CARDS_GREEN")
