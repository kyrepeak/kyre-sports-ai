from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header, HEADER_CSS

header = build_passing_yards_header(
    slate_label="NFL • PASSING YARDS",
    date_label="SUNDAY • SEP 20",
    slate_context="Week slate",
    status_label="Live data",
)
html = build_universal_shell(header)

assert 'data-py-layered-shell="true"' in html
assert 'data-py-step3-header="true"' in html
assert html.count('data-py-step3-header="true"') == 1
assert '<h1 class="ks-py-title">Passing Yards</h1>' in html
assert 'Quarterback projection hub' in html
assert 'data-py-slate-area="true"' in html
assert 'SUNDAY • SEP 20' in html
assert 'data-py-header-controls="true"' in html
for label in ("ALL QBs", "HOME", "AWAY", "AVAILABLE", "Live data"):
    assert label in html
assert '@media (max-width:760px)' in HEADER_CSS
assert '@media (max-width:460px)' in HEADER_CSS
assert 'data-qb-card=' not in html
assert 'data-qb-card-grid=' not in html

print("PASSING_YARDS_LAYERED_HUB_STEP3_HEADER_GREEN")
