"""Kyre Sports AI main entrypoint — WNBA PRA V2.8.2 + MLB Slate V3.2 + Hit UI V13.3 + HR V1.1 + H+R+RBI V1.0.1 + Pitcher K V1.0.5 + Moneyline V16.3 + Spread V15.5 + Totals V17.3 + Live V19.3.

Loads the proven V2.6 league-aware shell, keeps WNBA → PRA frozen on the hardened
V2.8.2 route, isolates MLB Slate through a V3.2 direct-loader wrapper, isolates
MLB 1+ Hit through its own V13.3 full-slate wrapper, isolates MLB Home Run through
calibrated V1.1, isolates MLB Hits + Runs + RBIs through joint-event V1.0.1,
isolates MLB Pitcher Strikeouts through workload-first V1.0.5, isolates MLB
Moneyline through V16.3, MLB Spread through V15.5, MLB Totals through V17.3,
and MLB Live Game through V19.3.
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
new_route = "from wnba_pra_hub_v282 import render_wnba_pra_hub"
if old_route not in source:
    raise RuntimeError("V2.8.2 direct-route bridge could not locate the V2.6 WNBA PRA import.")
source = source.replace(old_route, new_route, 1)

old_schedule_import = "from schedule_future import current_selected_date, games_for_date, render_slate_date_control"
new_schedule_import = "from mlb_schedule_v32 import current_selected_date, games_for_date, render_slate_date_control"
if old_schedule_import in source:
    source = source.replace(old_schedule_import, new_schedule_import, 1)

old_slate_import = "from slate_hub_v2091 import render_slate_hub"
new_slate_import = "from mlb_slate_hub_v32 import render_slate_hub"
if old_slate_import in source:
    source = source.replace(old_slate_import, new_slate_import, 1)

old_hit_import = "from hit_hub_v131 import render_hit_hub"
new_hit_import = "from mlb_hit_hub_v133 import render_hit_hub"
if old_hit_import in source:
    source = source.replace(old_hit_import, new_hit_import, 1)

old_ml_import = "from moneyline_hub_v162 import render_moneyline_hub"
new_ml_import = "from mlb_moneyline_hub_v163 import render_moneyline_hub"
if old_ml_import in source:
    source = source.replace(old_ml_import, new_ml_import, 1)

old_spread_import = "from spread_hub_v154 import render_spread_hub"
new_spread_import = "from mlb_spread_hub_v155 import render_spread_hub"
if old_spread_import in source:
    source = source.replace(old_spread_import, new_spread_import, 1)

old_totals_import = "from totals_hub_v172 import render_totals_hub"
new_totals_import = "from mlb_totals_hub_v173 import render_totals_hub"
if old_totals_import in source:
    source = source.replace(old_totals_import, new_totals_import, 1)

old_live_import = "from live_game_hub_v1921 import render_live_hub"
new_live_import = "from mlb_live_hub_v193 import render_live_hub"
if old_live_import in source:
    source = source.replace(old_live_import, new_live_import, 1)

source = source.replace(
    '                "Hits + Runs + RBIs",\n                "Moneyline",',
    '                "Hits + Runs + RBIs",\n                "Pitcher Strikeouts",\n                "Moneyline",',
    1,
)

market_marker = '''    elif market == "Live Game":
        from mlb_live_hub_v193 import render_live_hub
        render_live_hub(games_df, section_header, status_info, team_logo, h)
    else:
'''
market_routes = '''    elif market == "Live Game":
        from mlb_live_hub_v193 import render_live_hub
        render_live_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Home Run":
        from mlb_hr_hub_v11 import render_home_run_hub
        render_home_run_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Hits + Runs + RBIs":
        from mlb_hrrbi_hub_v101 import render_hrrbi_hub
        render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Pitcher Strikeouts":
        from mlb_pitcher_k_hub_v105 import render_pitcher_k_hub
        render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    else:
'''
if market_marker not in source:
    raise RuntimeError("MLB production-route bridge could not locate the Live/placeholder boundary.")
source = source.replace(market_marker, market_routes, 1)

source = source.replace("WNBA PRA V2.6", "WNBA PRA V2.8.2")
source = source.replace("PRA V2.6", "PRA V2.8.2")
source = source.replace("Hit UI V13.1", "Hit UI V13.3 • HR V1.1 • H+R+RBI V1.0.1 • Pitcher K V1.0.5")
source = source.replace("Moneyline V16.2", "Moneyline V16.3")
source = source.replace("ML V16.2", "ML V16.3")
source = source.replace("Spread V15.4", "Spread V15.5")
source = source.replace("Totals V17.2", "Totals V17.3")
source = source.replace("Live V19.2", "Live V19.3")
source = source.replace(
    "kyre_sports_ai_wnba_pra_v2_6_matchup_context_touch_nav.py",
    "kyre_sports_ai_wnba_pra_v2_8_2_mlb_slate_v3_2_hit_v13_3_hr_v1_1_hrrbi_v1_0_1_pitcher_k_v1_0_5_ml_v16_3_spread_v15_5_totals_v17_3_live_v19_3.py",
)

exec(
    compile(source, "kyre_sports_ai_wnba_pra_v2_8_2_mlb_slate_v3_2_hit_v13_3_hr_v1_1_hrrbi_v1_0_1_pitcher_k_v1_0_5_ml_v16_3_spread_v15_5_totals_v17_3_live_v19_3.py", "exec"),
    globals(),
    globals(),
)
