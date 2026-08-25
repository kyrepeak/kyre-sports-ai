"""Kyre Sports AI — WNBA Live Games Step-1 routing wrapper.

This entrypoint preserves the exact application from commit
235d7ddc47de93657910a1f0cf9928f2a9f0f758 (which itself preserves all frozen
MLB/WNBA/NFL production routes) and adds one isolated WNBA navigation target:

    Live Games -> wnba_live_hub_v1

Only navigation/routing is changed. The new page stops the frozen replay before
any existing WNBA market model is invoked. Existing Points, Rebounds, Assists,
Rebounds + Assists, PRA, Spread, Moneyline, Game Total, Daily Picks, MLB and NFL
routes remain owned by the preserved application.
"""
from __future__ import annotations

import subprocess
import urllib.request


PREVIOUS_APP_COMMIT = "235d7ddc47de93657910a1f0cf9928f2a9f0f758"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)


def _load_previous_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{PREVIOUS_APP_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_previous_app()

# 1) Add a fully isolated render boundary beside the existing R+A boundary.
route_anchor = '''    wnba_ra_v1.render_wnba_ra_hub(None, None, None, None)\n    st.stop()\n\n\ndef _sport_selectbox_with_nfl'''
route_replacement = '''    wnba_ra_v1.render_wnba_ra_hub(None, None, None, None)\n    st.stop()\n\n\ndef _render_wnba_live_route():\n    """Render only WNBA Live Games Step 1 and stop all frozen market replay."""\n    for name in list(sys.modules):\n        if name.startswith("wnba_live_"):\n            sys.modules.pop(name, None)\n    importlib.invalidate_caches()\n\n    import wnba_live_hub_v1 as wnba_live_v1\n\n    wnba_live_v1.render_wnba_live_hub(None, None, None, None)\n    st.stop()\n\n\ndef _sport_selectbox_with_nfl'''
if route_anchor not in source:
    raise RuntimeError("WNBA Live Step-1 route anchor not found in preserved app.")
source = source.replace(route_anchor, route_replacement, 1)

# 2) Add Live Games to the WNBA market selector immediately before Daily Picks.
menu_anchor = '''            values.insert(insert_at, ra_market)\n        options = values'''
menu_replacement = '''            values.insert(insert_at, ra_market)\n\n        live_market = "Live Games"\n        if live_market not in values:\n            try:\n                live_insert_at = values.index("Daily Picks")\n            except ValueError:\n                live_insert_at = len(values)\n            values.insert(live_insert_at, live_market)\n        options = values'''
if menu_anchor not in source:
    raise RuntimeError("WNBA Live Step-1 menu anchor not found in preserved app.")
source = source.replace(menu_anchor, menu_replacement, 1)

# 3) Intercept the new selection before the historical WNBA shell can render any
# pregame model. R+A keeps its existing isolated behavior.
selection_anchor = '''    if is_wnba_market_widget and str(selected) == "Rebounds + Assists":\n        _render_wnba_ra_route()\n\n    return selected'''
selection_replacement = '''    if is_wnba_market_widget and str(selected) == "Rebounds + Assists":\n        _render_wnba_ra_route()\n    if is_wnba_market_widget and str(selected) == "Live Games":\n        _render_wnba_live_route()\n\n    return selected'''
if selection_anchor not in source:
    raise RuntimeError("WNBA Live Step-1 selection anchor not found in preserved app.")
source = source.replace(selection_anchor, selection_replacement, 1)

# Syntax preflight before any preserved application side effects execute.
compile(source, "<kyre_preflight_plus_wnba_live_v1>", "exec")

exec(
    compile(
        source,
        "kyre_preserved_app_plus_wnba_live_games_v1_step1.py",
        "exec",
    ),
    globals(),
    globals(),
)
