"""Kyre Sports AI main entrypoint.

League-aware shell: MLB data is loaded only when MLB is selected. WNBA PRA uses
its own WNBA-only guarded data layer with the V2.4 verified-schedule command center.
WNBA PRA is rendered only when the WNBA PRA market is selected. Existing MLB
modules remain unchanged.
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
games_df = pd.DataFrame()
'''
if old_data_block not in source:
    raise RuntimeError("League-aware bridge could not locate the original data bootstrap.")
source = source.replace(old_data_block, new_data_block, 1)

mlb_marker = '''# ============================================================
# MLB
# ============================================================
'''
league_bootstrap = '''# ============================================================
# LEAGUE-AWARE DATA BOOTSTRAP
# ============================================================
if sport == "MLB":
    render_hero(game_date)
    game_date = render_slate_date_control()
    try:
        games_df = games_for_date(game_date)
    except requests.RequestException:
        games_df = pd.DataFrame()
else:
    games_df = pd.DataFrame()

'''
if mlb_marker not in source:
    raise RuntimeError("League-aware bridge could not locate the MLB section marker.")
source = source.replace(mlb_marker, league_bootstrap + mlb_marker, 1)

source = source.replace(
    'with st.expander("⚾ Today’s MLB schedule", expanded=False):',
    'with st.expander(f"✅ Verified MLB schedule • {game_date}", expanded=False):',
    1,
)

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

# Replace the old narrow three-column dropdown row with a mobile-first two-column
# navigation strip. WNBA defaults directly to PRA, so switching leagues is one tap
# and the PRA market is already selected. Both controls receive large touch targets.
nav_start = source.find('nav1, nav2, nav3 = st.columns([1.05, 1.55, 1.0])')
nav_end = source.find('\n\n# ============================================================\n# MLB', nav_start)
if nav_start == -1 or nav_end == -1:
    raise RuntimeError("Touch-nav bridge could not locate the original sport/market navigation.")

touch_nav = r'''st.markdown(
    """
    <style>
    .ks-touch-nav-note{
        margin:2px 0 10px;
        color:#8fa1bd;
        font-size:.72rem;
        font-weight:750;
    }
    div[data-testid="stSelectbox"] label p{
        color:#dbeafe !important;
        font-size:.78rem !important;
        font-weight:900 !important;
        letter-spacing:.055em !important;
        text-transform:uppercase !important;
        margin-bottom:5px !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
        min-height:58px !important;
        border-radius:15px !important;
        border:1px solid rgba(56,189,248,.28) !important;
        background:linear-gradient(180deg,rgba(22,32,51,.98),rgba(13,21,36,.98)) !important;
        box-shadow:0 8px 24px rgba(0,0,0,.13) !important;
        padding-left:6px !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span{
        font-size:1rem !important;
        font-weight:850 !important;
        color:#f8fafc !important;
    }
    .ks-nav-version{
        display:flex;
        justify-content:center;
        align-items:center;
        min-height:34px;
        margin:3px 0 8px;
        color:#8fa1bd;
        font-size:.68rem;
        font-weight:800;
    }
    .ks-wnba-active{
        display:flex;
        align-items:center;
        gap:7px;
        margin:2px 0 9px;
        padding:8px 11px;
        border:1px solid rgba(244,114,182,.22);
        border-radius:12px;
        color:#f9a8d4;
        background:rgba(244,114,182,.055);
        font-size:.72rem;
        font-weight:850;
    }
    @media(max-width:640px){
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
            min-height:62px !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] span{
            font-size:1.05rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

nav1, nav2 = st.columns([1, 1], gap="small")
with nav1:
    sport = st.selectbox(
        "🏟️ Sport",
        ["MLB", "WNBA"],
        key="ks_sport_touch",
    )
with nav2:
    if sport == "MLB":
        market = st.selectbox(
            "🎯 Market",
            [
                "Slate",
                "1+ Hit",
                "2+ Hits",
                "Home Run",
                "Hits + Runs + RBIs",
                "Moneyline",
                "Run Line",
                "Game Total",
                "Live Game",
            ],
            key="ks_mlb_market_touch",
        )
    else:
        market = st.selectbox(
            "🎯 WNBA Market",
            ["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total"],
            index=3,
            key="ks_wnba_market_touch",
        )

if sport == "WNBA" and market == "PRA":
    st.markdown(
        '<div class="ks-wnba-active">🏀 WNBA <b>→</b> PRA active • switching to WNBA opens PRA by default</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="ks-nav-version">Kyre Sports AI • touch navigation</div>',
        unsafe_allow_html=True,
    )'''

source = source[:nav_start] + touch_nav + source[nav_end:]

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
        render_slate_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Moneyline":
        from moneyline_hub_v162 import render_moneyline_hub
        render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Run Line":
        from spread_hub_v154 import render_spread_hub
        render_spread_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Game Total":
        from totals_hub_v172 import render_totals_hub
        render_totals_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Live Game":
        from live_game_hub_v1921 import render_live_hub
        render_live_hub(games_df, section_header, status_info, team_logo, h)
    else:
        section_header(f"MLB {market}", "This market module is not built yet.")
        st.info("The production models currently cover MLB Slate V20.9.1, 1+ Hit V13 / UI V13.1, Moneyline V16.2, Run Line V15.4, Game Totals V17.2 and Live Game V19.2.")
'''
if old_market_block not in source:
    raise RuntimeError("MLB module bridge could not locate the market placeholder.")
source = source.replace(old_market_block, new_market_block, 1)

old_wnba_block = '''else:
    section_header(f"WNBA {market}", "WNBA model workspace")
    st.info(
        "The WNBA interface is ready for its own model modules. MLB V13 remains unchanged."
    )
'''
new_wnba_block = '''else:
    if market == "PRA":
        from wnba_pra_hub_v24 import render_wnba_pra_hub

        render_wnba_pra_hub(
            section_header,
            status_info,
            None,
            h,
        )
        st.stop()
    else:
        section_header(f"WNBA {market}", "WNBA market module")
        st.info(f"WNBA {market} is separate from the PRA Command Center and will get its own model module.")
        st.stop()
'''
if old_wnba_block not in source:
    raise RuntimeError("WNBA PRA bridge could not locate the original WNBA placeholder.")
source = source.replace(old_wnba_block, new_wnba_block, 1)

source = source.replace(
    "V13 • UI 14.2</div>",
    "V13 • Hit UI V13.1 • WNBA PRA V2.4 • UI 14.2 • Slate V20.9.1 • ML V16.2 • Spread V15.4 • Totals V17.2 • Live V19.2 • Verified Future +30d</div>",
    1,
)
source = source.replace(
    "<b>KYRE SPORTS AI</b> • Model V13 • UI V14.2",
    "<b>KYRE SPORTS AI</b> • WNBA PRA V2.4 • Slate V20.9.1 • Hit V13 / UI V13.1 • Moneyline V16.2 • Spread V15.4 • Totals V17.2 • Live V19.2 • Verified Future Slates +30d • UI V14.2",
    1,
)

exec(
    compile(source, "kyre_sports_ai_wnba_pra_v2_4_verified_schedule_touch_nav.py", "exec"),
    globals(),
    globals(),
)
