"""Kyre Sports AI main entrypoint — WNBA PRA V2.8.2 + MLB schedule V3.1.

Loads the proven V2.6 league-aware shell, routes WNBA → PRA through the hardened
V2.8.2 usage/minutes layer, and routes MLB schedule loading through the isolated
MLB V3.1 schedule module. Existing MLB market models remain unchanged.
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

# WNBA PRA route remains frozen/unchanged while MLB is repaired.
old_route = "from wnba_pra_hub_v26 import render_wnba_pra_hub"
new_route = "from wnba_pra_hub_v282 import render_wnba_pra_hub"
if old_route not in source:
    raise RuntimeError("V2.8.2 direct-route bridge could not locate the V2.6 WNBA PRA import.")
source = source.replace(old_route, new_route, 1)

# MLB-only isolated schedule route. New module name forces a fresh import on
# Streamlit deploy instead of reusing a stale schedule_future_v3 module object.
old_schedule_import = "from schedule_future import current_selected_date, games_for_date, render_slate_date_control"
new_schedule_import = "from mlb_schedule_v31 import current_selected_date, games_for_date, render_slate_date_control"
if old_schedule_import in source:
    source = source.replace(old_schedule_import, new_schedule_import, 1)

source = source.replace("WNBA PRA V2.6", "WNBA PRA V2.8.2")
source = source.replace("PRA V2.6", "PRA V2.8.2")
source = source.replace(
    "kyre_sports_ai_wnba_pra_v2_6_matchup_context_touch_nav.py",
    "kyre_sports_ai_wnba_pra_v2_8_2_mlb_schedule_v3_1.py",
)

exec(
    compile(source, "kyre_sports_ai_wnba_pra_v2_8_2_mlb_schedule_v3_1.py", "exec"),
    globals(),
    globals(),
)
