"""Kyre Sports AI main entrypoint.

V15.1 bridge: preserve the proven V14.2/V13 main UI exactly, while wiring the
existing MLB -> Run Line dropdown into the V15 spread hub with both the daily
scanner and single-game analyzer.

The pinned source is the V14.2 app commit. We load it from local git history
when available (fast/no network) and fall back to the immutable raw GitHub
commit on shallow deployments such as Streamlit Cloud.
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

old_block = '''    else:
        section_header(
            f"MLB {market}",
            "This market module is not built yet.",
        )
        st.info("The production model currently covers MLB 1+ Hit.")
'''

new_block = '''    elif market == "Run Line":
        from spread_hub import render_spread_hub

        render_spread_hub(
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
        st.info("The production models currently cover MLB 1+ Hit and Run Line V15.1.")
'''

if old_block not in source:
    raise RuntimeError("V15.1 bridge could not locate the Run Line placeholder in the pinned UI source.")

source = source.replace(old_block, new_block, 1)
source = source.replace(
    "V13 • UI 14.2</div>",
    "V13 • UI 14.2 • Spread V15.1</div>",
    1,
)
source = source.replace(
    "<b>KYRE SPORTS AI</b> • Model V13 • UI V14.2",
    "<b>KYRE SPORTS AI</b> • Hit Model V13 • Spread V15.1 • UI V14.2",
    1,
)

exec(compile(source, "kyre_sports_ai_v15_1.py", "exec"), globals(), globals())
