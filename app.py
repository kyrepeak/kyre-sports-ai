"""Kyre Sports AI main entrypoint.

Verified future-slate bridge: preserve the proven V14.2/V13 base engine, add a
V20.9.1 dedicated MLB slate command center with records/L10/L5/H2H,
lineup/batting-average and pitcher intelligence, strict full-game market
matching, best-price/movement tracking, model-vs-market ML/run-line/total
edge grading, a whole-slate summary bar, same-book no-vig calibration, quote
freshness status and stale-signal protection, plus the V20.9 recursion hotfix;
route MLB 1+ Hit through the V13.1 mobile-first command center while preserving
the V13 probability engine and calibration history; add a WNBA PRA V2 official-
data foundation with official schedule, player stats, recent form, on-demand
rosters and empirical correlated PRA baselines; keep live sportsbook market sync
across moneyline/run-line/totals, V19.2 live intelligence, and use a strict
official-MLB date selector for future slates.
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

# Make Slate a first-class MLB destination while preserving every existing market.
source = source.replace(
    '                "1+ Hit",\n',
    '                "Slate",\n                "1+ Hit",\n',
    1,
)
source = source.replace(
    '                "Game Total",\n',
    '                "Game Total",\n                "Live Game",\n',
    1,
)

# Route 1+ Hit to the V13.1 command center. Keep the old V13 branch in the
# compiled source under an unreachable market value as a rollback-safe fallback.
source = source.replace(
    '    if market == "1+ Hit":\n',
    '''    if market == "1+ Hit":
        from hit_hub_v131 import render_hit_hub

        render_hit_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "__LEGACY_1+ HIT":
''',
    1,
)

old_market_block = '''    else:
        section_header(
            f"MLB {market}",
            "This market module is not built yet.",
        )
        st.info("The production model currently covers MLB 1+ Hit.")
'''

new_market_block = '''    elif market == "Slate":
        from slate_hub_v2091 import render_slate_hub

        render_slate_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Moneyline":
        from moneyline_hub_v162 import render_moneyline_hub

        render_moneyline_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Run Line":
        from spread_hub_v154 import render_spread_hub

        render_spread_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Game Total":
        from totals_hub_v172 import render_totals_hub

        render_totals_hub(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    elif market == "Live Game":
        from live_game_hub_v1921 import render_live_hub

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
        st.info("The production models currently cover MLB Slate V20.9.1, 1+ Hit V13 / UI V13.1, Moneyline V16.2, Run Line V15.4, Game Totals V17.2 and Live Game V19.2.")
'''

if old_market_block not in source:
    raise RuntimeError("Verified future-slate bridge could not locate the market placeholder.")
source = source.replace(old_market_block, new_market_block, 1)

old_wnba_block = '''else:
    section_header(f"WNBA {market}", "WNBA model workspace")
    st.info(
        "The WNBA interface is ready for its own model modules. MLB V13 remains unchanged."
    )
'''
new_wnba_block = '''else:
    from wnba_pra_hub_v2 import render_wnba_pra_hub

    render_wnba_pra_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )
'''
if old_wnba_block not in source:
    raise RuntimeError("WNBA PRA bridge could not locate the original WNBA placeholder.")
source = source.replace(old_wnba_block, new_wnba_block, 1)

source = source.replace(
    "V13 • UI 14.2</div>",
    "V13 • Hit UI V13.1 • WNBA PRA V2 • UI 14.2 • Slate V20.9.1 • ML V16.2 • Spread V15.4 • Totals V17.2 • Live V19.2 • Live Edge Board • Verified Future +30d</div>",
    1,
)
source = source.replace(
    "<b>KYRE SPORTS AI</b> • Model V13 • UI V14.2",
    "<b>KYRE SPORTS AI</b> • WNBA PRA V2 • Slate V20.9.1 • Hit V13 / UI V13.1 • Moneyline V16.2 • Spread V15.4 • Totals V17.2 • Live V19.2 • Live Edge Board • Verified Future Slates +30d • UI V14.2",
    1,
)

exec(compile(source, "kyre_sports_ai_wnba_pra_v2_hit_v13_1_slate_v20_9_1.py", "exec"), globals(), globals())
