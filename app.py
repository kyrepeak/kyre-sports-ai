'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA PRA V3.2.1 frozen + WNBA Points V1.9.8.4.1 durable calibration persistence + WNBA Rebounds V1.0 Step 1.

Frozen production checkpoints:
- MLB V2.1.7: branch mlb-v217-frozen-20260818
- WNBA PRA V3.2.1: branch wnba-pra-v321-frozen-20260818
  commit 5f29fc48856a198d74bcdbde47821e55e275222a
- WNBA Points validated live model/display V1.9.8.2:
  branch wnba-points-v1982-frozen-20260818
  commit a16c37962f4aecaa1941786718544b0432623734

WNBA Points V1.9.8.4.1 keeps the validated V1.9.8.2 projection, SportsGameOdds,
Monte Carlo, uncertainty floor, rich cards, opponent identity and role display
frozen. V1.9.8.3 remains the observational out-of-sample calibration lab.
V1.9.8.4 adds atomic primary/backup server files, a session working copy and
compressed checksummed browser copies. V1.9.8.4.1 fixes browser hydration/readback
without changing model math. No historical calibrator can change live probabilities
until minimum sample/slate gates and chronological holdout validation pass.

WNBA Rebounds V1.0 is isolated and activates only Step 1: verified Eastern-date
schedule reconciliation. No Rebounds projection, sportsbook grading or simulation
is enabled yet.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v321 as wnba_pra_v321
import wnba_points_hub_v19841 as wnba_points_v19841

BASE_COMMIT = "06d34032b9608cba07072b02934ae3a4b7d7c295"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{BASE_COMMIT}/app.py"
)

_ORIGINAL_CHECK_OUTPUT = subprocess.check_output

_OLD_WNBA_PLACEHOLDER = '''    else:
        section_header(f"WNBA {market}", "WNBA market module")
        st.info(f"WNBA {market} is separate from the PRA Command Center and will get its own model module.")
        st.stop()
'''

_NEW_WNBA_PLACEHOLDER = '''    elif market == "Points":
        from wnba_points_hub_v19841 import render_wnba_points_hub

        render_wnba_points_hub(
            section_header,
            status_info,
            None,
            h,
        )
        st.stop()
    elif market == "Rebounds":
        from wnba_rebounds_hub_v10 import render_wnba_rebounds_hub

        render_wnba_rebounds_hub(
            section_header,
            status_info,
            None,
            h,
        )
        st.stop()
    else:
        section_header(f"WNBA {market}", "WNBA market module")
        st.info(f"WNBA {market} is separate from the frozen PRA Command Center and will get its own production model page.")
        st.stop()
'''


def _patch_inherited_app_text(value):
    'Patch only WNBA Points/Rebounds routing inside inherited app shells.'
    is_bytes = isinstance(value, (bytes, bytearray))
    text = value.decode("utf-8") if is_bytes else str(value)

    for old_module in (
        "wnba_points_hub_v11", "wnba_points_hub_v12", "wnba_points_hub_v13",
        "wnba_points_hub_v14", "wnba_points_hub_v15", "wnba_points_hub_v151",
        "wnba_points_hub_v16", "wnba_points_hub_v17", "wnba_points_hub_v171",
        "wnba_points_hub_v18", "wnba_points_hub_v19", "wnba_points_hub_v191",
        "wnba_points_hub_v192", "wnba_points_hub_v193", "wnba_points_hub_v194",
        "wnba_points_hub_v195", "wnba_points_hub_v196", "wnba_points_hub_v197",
        "wnba_points_hub_v198", "wnba_points_hub_v1981", "wnba_points_hub_v1982",
        "wnba_points_hub_v1983", "wnba_points_hub_v1984",
    ):
        text = text.replace(
            f"from {old_module} import render_wnba_points_hub",
            "from wnba_points_hub_v19841 import render_wnba_points_hub",
        )

    if "wnba_points_hub_v19841" not in text and _OLD_WNBA_PLACEHOLDER in text:
        text = text.replace(_OLD_WNBA_PLACEHOLDER, _NEW_WNBA_PLACEHOLDER, 1)
    return text.encode("utf-8") if is_bytes else text


def _deep_shell_check_output(*args, **kwargs):
    result = _ORIGINAL_CHECK_OUTPUT(*args, **kwargs)
    try:
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
            if str(cmd[0]) == "git" and str(cmd[1]) == "show" and str(cmd[2]).endswith(":app.py"):
                return _patch_inherited_app_text(result)
    except Exception:
        pass
    return result


subprocess.check_output = _deep_shell_check_output

# Cache-safe compatibility aliases for every legacy Points page name. V1.9.8.4.1
# imports the genuine V1.9.8.4/V1.9.8.3/V1.9.8.2 modules before aliases install.
for _legacy in (
    "wnba_points_hub_v11", "wnba_points_hub_v12", "wnba_points_hub_v13",
    "wnba_points_hub_v14", "wnba_points_hub_v15", "wnba_points_hub_v151",
    "wnba_points_hub_v16", "wnba_points_hub_v17", "wnba_points_hub_v171",
    "wnba_points_hub_v18", "wnba_points_hub_v19", "wnba_points_hub_v191",
    "wnba_points_hub_v192", "wnba_points_hub_v193", "wnba_points_hub_v194",
    "wnba_points_hub_v195", "wnba_points_hub_v196", "wnba_points_hub_v197",
    "wnba_points_hub_v198", "wnba_points_hub_v1981", "wnba_points_hub_v1982",
    "wnba_points_hub_v1983", "wnba_points_hub_v1984",
):
    sys.modules[_legacy] = wnba_points_v19841


def _load_previous_app():
    try:
        return subprocess.check_output(
            ["git", "show", f"{BASE_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return _patch_inherited_app_text(response.read().decode("utf-8"))


source = _load_previous_app()
old = "from mlb_daily_game_picks_v198 import render_daily_game_picks"
new = "from mlb_daily_game_picks_v217_guard import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.8", "Daily Game Picks V2.1.7", 1)
source = source.replace("WNBA Points V1.9.3", "WNBA Points V1.9.8.4.1", 1)

# Cache-safe PRA route stays pinned to the frozen V3.2.1 implementation.
sys.modules["wnba_pra_hub_v282"] = wnba_pra_v321

# Frozen MLB sportsbook routing stays exactly as before.
slate_multi_provider.install()

exec(
    compile(source, "kyre_sports_ai_mlb_v217_wnba_pra_v321_points_v19841_rebounds_v10.py", "exec"),
    globals(),
    globals(),
)
