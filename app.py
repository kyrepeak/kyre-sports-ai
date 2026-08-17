"""Kyre Sports AI main entrypoint.

Verified future-slate bridge: preserve the proven V14.2/V13 main UI, keep the
spread engine, add V16.1 moneyline history/form views, V17.1 game-total O/U
rankings and V18.2 live game state, and use a strict official-MLB date selector
for tomorrow and future slates.
"""

import subprocess
import urllib.request

BASE_COMMIT = "98be55479d4d5f58b6f0d9d307a5fa20351c09ba"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{BASE_COMMIT}/app.py"
)


def _load_v14_source():
    try:
        return subprocess.check_output(
            ["git", "show", f"{BASE_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_v14_source()

old_data_block = '''try:
    games_df, game_date = games_today()
except requests.RequestException:
    games_df = pd.DataFrame()
    game_date = datetime.now(ET).strftime("%Y-%m-%d")

render_hero(game_date)
'''

new_data_block = '''from schedule_future import current_selected_date, games_for_date, render_slate_date_control

game_date = current_selected_date()
render_hero(game_date)
game_date = render_slate_date_control()
try:
    games_df = games_for_date(game_date)
except requests.RequestException:
    games_df = pd.DataFrame()
'''

if old_data_block not in source:
    raise RuntimeError("Verified future-slate bridge could not locate the original today-only schedule block.")
source = source.replace(old_data_block, new_data_block, 1)

source = source.replace(
    'with st.expander("⚾ Today’s MLB schedule", expanded=False):',
    'with st.expander(f"✅ Verified MLB schedule • {game_date}", expanded=False):',
    1,
)

source = source.replace(
    '                "Game Total",\n',
    '                "Game Total",\n                "Live Game",\n',
    1,
)

old_market_block = '''    else:
        section_header(
            f"MLB {market}",
            "This market module is not built yet.",
        )
        st.info("The production model currently covers MLB 1+ Hit.")
'''

new_market_block = '''    elif market == "Moneyline":
        from moneyline_hub_v161 import render_moneyline_hub

        render_moneyline_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Run Line":
        from spread_hub_v153 import render_spread_hub

        render_spread_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Game Total":
        from totals_hub_v171 import render_totals_hub

        render_totals_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Live Game":
        from live_game_hub_v182 import render_live_hub

        render_live_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    else:
        section_header(
            f"MLB {market}",
            "This market module is not built yet.",
        )
        st.info("The production models currently cover MLB 1+ Hit, Moneyline V16.1, Run Line V15.3.1, Game Totals V17.1 and Live Game V18.2.")
'''

if old_market_block not in source:
    raise RuntimeError("Verified future-slate bridge could not locate the market placeholder.")
source = source.replace(old_market_block, new_market_block, 1)

source = source.replace(
    "V13 • UI 14.2</div>",
    "V13 • UI 14.2 • ML V16.1 • Spread V15.3.1 • Totals V17.1 • Live V18.2 • Verified Future +30d</div>",
    1,
)
source = source.replace(
    "<b>KYRE SPORTS AI</b> • Model V13 • UI V14.2",
    "<b>KYRE SPORTS AI</b> • Hit V13 • Moneyline V16.1 • Spread V15.3.1 • Totals V17.1 • Live V18.2 • Verified Future Slates +30d • UI V14.2",
    1,
)

exec(compile(source, "kyre_sports_ai_live_v18_2.py", "exec"), globals(), globals())
