"""Kyre Sports AI main entrypoint — WNBA PRA V2.8.2 + MLB Slate V3.2.

Loads the proven V2.6 league-aware shell, keeps WNBA → PRA frozen on the hardened
V2.8.2 route, and isolates MLB Slate through a V3.2 direct-loader wrapper.
No WNBA module is modified by the MLB repair path.
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

# Keep the MLB bootstrap on a fresh MLB-only schedule module.
old_schedule_import = "from schedule_future import current_selected_date, games_for_date, render_slate_date_control"
new_schedule_import = "from mlb_schedule_v32 import current_selected_date, games_for_date, render_slate_date_control"
if old_schedule_import in source:
    source = source.replace(old_schedule_import, new_schedule_import, 1)

# Crucial isolation: MLB Slate does not depend on the global bootstrap anymore.
# It reloads the selected MLB date itself and exposes provider diagnostics if empty.
old_slate_import = "from slate_hub_v2091 import render_slate_hub"
new_slate_import = "from mlb_slate_hub_v32 import render_slate_hub"
if old_slate_import in source:
    source = source.replace(old_slate_import, new_slate_import, 1)

source = source.replace("WNBA PRA V2.6", "WNBA PRA V2.8.2")
source = source.replace("PRA V2.6", "PRA V2.8.2")
source = source.replace(
    "kyre_sports_ai_wnba_pra_v2_6_matchup_context_touch_nav.py",
    "kyre_sports_ai_wnba_pra_v2_8_2_mlb_slate_v3_2.py",
)

exec(
    compile(source, "kyre_sports_ai_wnba_pra_v2_8_2_mlb_slate_v3_2.py", "exec"),
    globals(),
    globals(),
)
