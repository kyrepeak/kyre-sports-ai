from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyre_universal_shell_v1 import NAV_ITEMS, SHELL_VERSION, build_universal_shell

assert "BLACK + GLACIER BLUE" in SHELL_VERSION

html = build_universal_shell(
    '<section id="proof-content">HELLO SHELL</section>',
    active_nav="Passing Yards",
    slate_label="Sunday Slate",
    sport_label="NFL",
)

# Frozen Step 1 foundation is consumed.
assert 'data-kyre-universal-theme="v1"' in html
assert "--kyre-glacier:" in html
assert "--kyre-bg-0:" in html

# Step 2 shell contract.
assert html.count('data-kyre-universal-shell="v1"') == 1
assert html.count('data-kyre-shell-sidebar="true"') == 1
assert html.count('data-kyre-shell-topbar="true"') == 1
assert html.count('data-kyre-shell-main="true"') == 1
assert html.count('data-kyre-content-slot="true"') == 1
assert "KYRE <span>SPORTS AI</span>" in html
assert "Search players, teams, or games" in html
assert "Sunday Slate" in html
assert "LIVE DATA" in html
assert "HELLO SHELL" in html

# Navigation and active state.
for label, _icon in NAV_ITEMS:
    assert f'data-kyre-nav="{label}"' in html
assert 'data-kyre-nav="Passing Yards" aria-current="page"' in html
assert html.count('aria-current="page"') == 1

# Responsive contract.
assert "@media(max-width:980px)" in html
assert "@media(max-width:720px)" in html
assert "@media(max-width:430px)" in html
assert "grid-template-columns:248px minmax(0,1fr)" in html
assert ".kyre-universe-sidebar{display:none}" in html
assert "position:sticky" in html

# Scope safety: Step 2 is shell only.
source = Path("kyre_universal_shell_v1.py").read_text()
assert "streamlit_memory_lazy_router" not in source
assert "render_nfl_passing_yards_hub" not in source
assert "app.py" not in source

print("UNIVERSAL_THEME_STEP2_SHELL_GREEN")
