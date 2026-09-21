from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import kyre_universal_shell_runtime_v1 as runtime

assert "BLACK + GLACIER BLUE" in runtime.SITEWIDE_SHELL_VERSION

css = runtime.build_sitewide_shell_css()
for marker in (
    'data-kyre-universal-theme="v1"',
    'data-kyre-universal-components-css="v1"',
    'data-kyre-universal-responsive="v1"',
    'data-kyre-sitewide-shell="v1"',
):
    assert marker in css
assert '[data-testid="stSidebar"]' in css
assert '[data-testid="stHeader"]' in css
assert ".main .block-container" in css
assert "@media(max-width:720px)" in css

seen = {"main": [], "sidebar": []}

class _Sidebar:
    def markdown(self, body, **kwargs):
        seen["sidebar"].append((body, kwargs))

class _FakeSt:
    sidebar = _Sidebar()
    def markdown(self, body, **kwargs):
        seen["main"].append((body, kwargs))

original_st = runtime.st
runtime.st = _FakeSt()
try:
    runtime.activate_universal_shell()
finally:
    runtime.st = original_st

assert len(seen["main"]) == 2
assert len(seen["sidebar"]) == 1
assert 'data-kyre-sitewide-topbar="v1"' in seen["main"][1][0]
assert 'data-kyre-sitewide-sidebar="v1"' in seen["sidebar"][0][0]
assert all(row[1].get("unsafe_allow_html") is True for row in seen["main"] + seen["sidebar"])

app = Path("app.py").read_text()
assert "from kyre_universal_shell_runtime_v1 import activate_universal_shell" in app
assert "activate_universal_shell()" in app
assert "from streamlit_memory_lazy_router_v188 import record_bootstrap_import_ms, render_app" in app
assert app.index("activate_universal_shell()") < app.index("    render_app()")
assert "SITEWIDE_UNIVERSAL_SHELL_RUNTIME" in app

# Scope safety: shell activation must not replace the router or mutate sports logic.
source = Path("kyre_universal_shell_runtime_v1.py").read_text().lower()
for forbidden in (
    "prop_hubs",
    "projection",
    "probability",
    "requests.get(",
    "requests.post(",
    "render_nfl",
    "render_cfb",
    "render_wnba",
    "render_mlb",
):
    assert forbidden not in source

print("SITEWIDE_THEME_ROLLOUT_STEP1_SHELL_GREEN")
