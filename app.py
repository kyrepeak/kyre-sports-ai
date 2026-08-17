"""Kyre Sports AI main entrypoint — WNBA PRA V2.8.1 direct route.

Loads the proven V2.6 league-aware shell, then routes WNBA → PRA directly to the
V2.8.1 projected-minutes + usage hotfix. MLB modules remain unchanged.
"""

import subprocess
import urllib.request

BASE_COMMIT = "07d261c1970204ce16fcfe98ef6488f5f1f0a3e7"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{BASE_COMMIT}/app.py"
)


def _load_v26_shell():
    try:
        return subprocess.check_output(
            ["git", "show", f"{BASE_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_v26_shell()

old_route = "from wnba_pra_hub_v26 import render_wnba_pra_hub"
new_route = "from wnba_pra_hub_v281 import render_wnba_pra_hub"
if old_route not in source:
    raise RuntimeError("V2.8.1 direct-route bridge could not locate the V2.6 WNBA PRA import.")
source = source.replace(old_route, new_route, 1)

source = source.replace("WNBA PRA V2.6", "WNBA PRA V2.8.1")
source = source.replace("PRA V2.6", "PRA V2.8.1")
source = source.replace(
    "kyre_sports_ai_wnba_pra_v2_6_matchup_context_touch_nav.py",
    "kyre_sports_ai_wnba_pra_v2_8_1_usage_touch_nav.py",
)

exec(
    compile(source, "kyre_sports_ai_wnba_pra_v2_8_1_direct_route.py", "exec"),
    globals(),
    globals(),
)
