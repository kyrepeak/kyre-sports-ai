'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA PRA V3.2.1 frozen + Points V1.4 active.

Loads the current known-good wrapper chain while preserving the frozen MLB V2.1.7
and WNBA PRA V3.2.1 checkpoints. WNBA Points is injected only when the inherited
league-aware shell reaches its real non-PRA WNBA placeholder.

Frozen checkpoints:
- MLB V2.1.7: branch mlb-v217-frozen-20260818
- WNBA PRA V3.2.1: branch wnba-pra-v321-frozen-20260818
  commit 5f29fc48856a198d74bcdbde47821e55e275222a

WNBA Points V1.4 uses the isolated ET-reconciled WNBA schedule V2.5. PRA totals
never feed the Points projection and Points is not yet fed into the shared WNBA
Final Card.

The deep-shell loader patch is deliberately narrow: it changes only inherited
WNBA Points routing. Legacy Points import names are pinned to V1.4 so Streamlit
cannot revive stale page modules through older wrappers. MLB model math, PRA model
math and all frozen connectors remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v321 as wnba_pra_v321
import wnba_points_hub_v14 as wnba_points_v14

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
        from wnba_points_hub_v14 import render_wnba_points_hub

        render_wnba_points_hub(
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
    """Patch only WNBA Points routing inside inherited app shells."""
    is_bytes = isinstance(value, (bytes, bytearray))
    text = value.decode("utf-8") if is_bytes else str(value)

    for old_module in ("wnba_points_hub_v11", "wnba_points_hub_v12", "wnba_points_hub_v13"):
        text = text.replace(
            f"from {old_module} import render_wnba_points_hub",
            "from wnba_points_hub_v14 import render_wnba_points_hub",
        )

    if "wnba_points_hub_v14" not in text and _OLD_WNBA_PLACEHOLDER in text:
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

# Cache-safe compatibility aliases for every legacy Points page name.
sys.modules["wnba_points_hub_v11"] = wnba_points_v14
sys.modules["wnba_points_hub_v12"] = wnba_points_v14
sys.modules["wnba_points_hub_v13"] = wnba_points_v14


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

# Cache-safe PRA route stays pinned to the frozen V3.2.1 implementation.
sys.modules["wnba_pra_hub_v282"] = wnba_pra_v321

# Frozen MLB sportsbook routing stays exactly as before.
slate_multi_provider.install()

exec(
    compile(source, "kyre_sports_ai_mlb_v217_wnba_pra_v321_frozen_points_v14_et_schedule.py", "exec"),
    globals(),
    globals(),
)
