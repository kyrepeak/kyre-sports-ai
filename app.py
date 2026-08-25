"""Kyre Sports AI — WNBA Live Games removed; pre-live production checkpoint restored.

This entrypoint intentionally removes WNBA Live Games from the running Streamlit
application and restores the exact application checkpoint immediately before the
Live Games route was introduced.

Frozen application checkpoint:
    235d7ddc47de93657910a1f0cf9928f2a9f0f758

Contracts
---------
- WNBA Live Games is not rendered, routed, or offered in navigation.
- No ``wnba_live_*`` module is imported by this entrypoint.
- Existing WNBA Points, Rebounds, Assists, Rebounds + Assists, PRA, Spread,
  Moneyline, Game Total and Daily Picks retain their frozen production behavior.
- Existing MLB and NFL routes remain exactly as they were at that checkpoint.
- A tiny PRA presentation-route refresh is allowed so additive current PRA card
  layers can hot-reload without restarting the whole Streamlit worker.
- No production projection, probability, Monte Carlo, calibration, ranking,
  qualification, or sportsbook logic is changed here.
- Historical ``wnba_live_*`` source files may remain in the repository as an
  archive, but they are unreachable from the app and consume no runtime memory
  after a clean process restart.
"""
from __future__ import annotations

import gc
import importlib
import subprocess
import sys
import urllib.request

import streamlit as st


FROZEN_PRE_LIVE_COMMIT = "235d7ddc47de93657910a1f0cf9928f2a9f0f758"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{FROZEN_PRE_LIVE_COMMIT}/app.py"
)


def _purge_live_runtime_state() -> None:
    """Remove stale Live-Games-only state left by earlier Streamlit reruns.

    This migration is deliberately narrow: it removes only the retired live-game
    route/session payloads and leaves every other WNBA/MLB/NFL state untouched.
    """
    if str(st.session_state.get("ks_wnba_market_touch") or "") == "Live Games":
        st.session_state.pop("ks_wnba_market_touch", None)

    live_prefixes = (
        "wnba_live_",
        "wnba_step6",
        "wnba_step63",
        "wnba_step64",
        "wnba_step65",
        "wnba_step651",
        "wnba_step66",
    )
    for key in list(st.session_state.keys()):
        if str(key).startswith(live_prefixes):
            st.session_state.pop(key, None)

    # A hot-reloaded Streamlit worker can still have old live modules resident
    # from the previous app version. Drop those references now; a process restart
    # guarantees they are fully absent thereafter.
    for name in list(sys.modules):
        if name.startswith("wnba_live_"):
            sys.modules.pop(name, None)

    gc.collect()


def _refresh_pra_presentation_route() -> None:
    """Reload only the current PRA presentation route on a hot Streamlit worker.

    The outer app intentionally executes a frozen pre-live source file. That
    frozen source imports ``wnba_pra_hub_v3612`` by its historical module name.
    Streamlit keeps Python modules resident across reruns, so changing the current
    v3612 compatibility wrapper on disk is not enough: an already-imported old
    module object can keep routing to the previous presentation indefinitely.

    Clear only the four tiny route/presentation modules that are allowed to move.
    The heavy PRA production/model stack remains resident and untouched.
    """
    for name in (
        "wnba_pra_hub_v321",          # historical alias installed by frozen app
        "wnba_pra_hub_v3612",         # frozen import name / current compat route
        "wnba_pra_hub_v3613",         # additive precision presentation hub
        "wnba_pra_opportunity_v3613", # additive card-only Step 1 helper
    ):
        sys.modules.pop(name, None)
    importlib.invalidate_caches()


def _load_frozen_pre_live_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{FROZEN_PRE_LIVE_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


_purge_live_runtime_state()
_refresh_pra_presentation_route()
source = _load_frozen_pre_live_app()

# Guard against accidentally pointing this wrapper at a checkpoint that already
# contained the retired page.
if "Live Games" in source or "wnba_live_" in source:
    raise RuntimeError("Frozen pre-live checkpoint unexpectedly contains WNBA Live Games.")

compile(source, "<kyre_frozen_pre_live_preflight>", "exec")
exec(
    compile(source, "kyre_sports_ai_frozen_without_wnba_live_games.py", "exec"),
    globals(),
    globals(),
)
