"""Kyre Sports AI main entrypoint — WNBA PRA V2.8.2 + MLB Slate V3.2 + Matchup Explorer V1.9 + Hit UI V13.3 + HR V1.1 + H+R+RBI V1.0.1 + Pitcher K V1.0.6 + Moneyline V16.3 + Spread V15.5 + Totals V17.3 + Live V19.3.
"""

import subprocess
import urllib.request

BASE_COMMIT = "07d261c1970204ce16fcfe98ef6488f5f1f0a3e7"
RAW_URL = "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/" f"{BASE_COMMIT}/app.py"

def _load_v26_shell():
    try:
        return subprocess.check_output(["git", "show", f"{BASE_COMMIT}:app.py"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")

source = _load_v26_shell()
repls = [
("from wnba_pra_hub_v26 import render_wnba_pra_hub","from wnba_pra_hub_v282 import render_wnba_pra_hub"),
("from schedule_future import current_selected_date, games_for_date, render_slate_date_control","from mlb_schedule_v32 import current_selected_date, games_for_date, render_slate_date_control"),
("from slate_hub_v2091 import render_slate_hub","from mlb_slate_hub_v32 import render_slate_hub"),
("from hit_hub_v131 import render_hit_hub","from mlb_hit_hub_v133 import render_hit_hub"),
("from moneyline_hub_v162 import render_moneyline_hub","from mlb_moneyline_hub_v163 import render_moneyline_hub"),
("from spread_hub_v154 import render_spread_hub","from mlb_spread_hub_v155 import render_spread_hub"),
("from totals_hub_v172 import render_totals_hub","from mlb_totals_hub_v173 import render_totals_hub"),
("from live_game_hub_v1921 import render_live_hub","from mlb_live_hub_v193 import render_live_hub"),
]
for a,b in repls:
    if a in source: source=source.replace(a,b,1)

source=source.replace('                "Hits + Runs + RBIs",\n                "Moneyline",','                "Hits + Runs + RBIs",\n                "Pitcher Strikeouts",\n                "Matchup Explorer",\n                "Moneyline",',1)
market_marker='''    elif market == "Live Game":
        from mlb_live_hub_v193 import render_live_hub
        render_live_hub(games_df, section_header, status_info, team_logo, h)
    else:
'''
market_routes='''    elif market == "Live Game":
        from mlb_live_hub_v193 import render_live_hub
        render_live_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Home Run":
        from mlb_hr_hub_v11 import render_home_run_hub
        render_home_run_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Hits + Runs + RBIs":
        from mlb_hrrbi_hub_v101 import render_hrrbi_hub
        render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Pitcher Strikeouts":
        from mlb_pitcher_k_hub_v106 import render_pitcher_k_hub
        render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Matchup Explorer":
        from mlb_matchup_hub_v19 import render_matchup_hub
        from mlb_schedule_v32 import load_with_diagnostics
        import streamlit as st
        try: matchup_day=str(current_selected_date())[:10]
        except Exception: matchup_day=None
        if not matchup_day or len(matchup_day)!=10:
            try: matchup_day=str(games_df.iloc[0].get("game_date"))[:10]
            except Exception: matchup_day=None
        if matchup_day:
            _matchup_games,_matchup_diag=load_with_diagnostics(matchup_day)
            if _matchup_games is not None and not _matchup_games.empty: games_df=_matchup_games
            elif games_df is None or games_df.empty: st.warning(f"Matchup Explorer schedule reload returned 0 games for {matchup_day}.")
        render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    else:
'''
if market_marker not in source: raise RuntimeError("MLB production-route bridge could not locate boundary.")
source=source.replace(market_marker,market_routes,1)
source=source.replace("WNBA PRA V2.6","WNBA PRA V2.8.2").replace("PRA V2.6","PRA V2.8.2")
source=source.replace("Hit UI V13.1","Hit UI V13.3 • Matchup Explorer V1.9 • HR V1.1 • H+R+RBI V1.0.1 • Pitcher K V1.0.6")
source=source.replace("Moneyline V16.2","Moneyline V16.3").replace("ML V16.2","ML V16.3").replace("Spread V15.4","Spread V15.5").replace("Totals V17.2","Totals V17.3").replace("Live V19.2","Live V19.3")
source=source.replace("kyre_sports_ai_wnba_pra_v2_6_matchup_context_touch_nav.py","kyre_sports_ai_v1_9.py")
exec(compile(source,"kyre_sports_ai_v1_9.py","exec"),globals(),globals())
