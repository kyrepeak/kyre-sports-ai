from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell, SHELL_CSS

html = build_universal_shell()

assert 'data-py-layered-shell="true"' in html
assert html.count('data-universal-topbar="true"') == 1
assert html.count('data-universal-sidebar="true"') == 1
assert html.count('data-universal-main="true"') == 1
assert html.count('data-shell-content-slot="true"') == 1
assert 'data-nav-label="Passing Yards"' in html
assert 'ks-rail-item is-active' in html
assert 'id="ks-shell-menu-toggle"' in html
assert 'for="ks-shell-menu-toggle"' in html
assert '@media (max-width:900px)' in SHELL_CSS
assert '#ks-shell-menu-toggle:checked ~ .ks-shell-rail{transform:translateX(0)}' in SHELL_CSS
assert '.ks-shell-main{min-height:100vh;margin-left:var(--ks-rail)' in SHELL_CSS
assert 'Hub content begins in Step 3' in html

print("PASSING_YARDS_LAYERED_HUB_STEP2_SHELL_GREEN")
