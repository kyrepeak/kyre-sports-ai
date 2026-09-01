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
- Step 7F installs an API-first read-only WNBA schedule bridge above the frozen
  replay. It preserves the exact V2.5 schedule frame contract and falls back to
  the original direct schedule transport if the hosted API cannot be consumed.
- MLB Live Odds adds one isolated read-only sidebar route after the real
  Streamlit page config completes; existing MLB model routes remain untouched.
- MLB Step 7B redirects only the frozen Spread V15.6 presentation import to the
  additive V15.7 exact-ID FanDuel Run Line API context wrapper.
- MLB Step 7C redirects only the frozen Moneyline V16.3 presentation boundary to
  the additive V16.4 exact-ID FanDuel Moneyline API context wrapper.
- MLB Step 7E redirects only the frozen Totals V17.3 presentation boundary to
  the additive V17.4 exact-ID FanDuel Game Total API context wrapper.
- No production projection, probability, Monte Carlo, calibration, ranking,
  qualification, sportsbook pricing, scheduler or write logic is changed here.
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


def _install_step7f_wnba_api_bridge() -> dict:
    """Install the read-only API schedule transport without risking app boot."""
    try:
        from wnba_api_schedule_bridge_v1 import install_wnba_api_schedule_bridge

        return install_wnba_api_schedule_bridge()
    except Exception as exc:
        # The bridge itself has a per-read legacy fallback. This outer guard also
        # ensures an import/configuration problem can never take down the frozen
        # Streamlit application before it renders.
        return {
            "installed": False,
            "model_version": "WNBA STREAMLIT API SCHEDULE BRIDGE V1",
            "error_type": type(exc).__name__,
            "legacy_app_boot_preserved": True,
        }


def _install_step18b_wnba_consumer_bridge() -> dict:
    """Route frozen Daily Picks to the certified read-only Step-18A consumer."""
    from wnba_step18b_consumer_bridge_v1 import install_step18b_consumer_bridge

    return install_step18b_consumer_bridge()


def _install_step18c_wnba_consumer_bridge() -> dict:
    """Install the reliability bridge; fail closed if its module cannot import."""
    try:
        sys.modules.pop("wnba_step18c_consumer_bridge_v1", None)
        importlib.invalidate_caches()
        from wnba_step18c_consumer_bridge_v1 import install_step18c_consumer_bridge

        return install_step18c_consumer_bridge()
    except Exception as exc:
        import types
        safe = types.ModuleType("wnba_daily_picks_hub_step18c_boot_fail_closed")
        safe.MODEL_VERSION = "WNBA DAILY PICKS STEP 18C BOOT FAIL-CLOSED"

        def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
            st.error("WNBA Daily Picks could not load the certified consumer presentation. No legacy computation or cached picks are being shown.")
            st.caption(f"Consumer presentation state: {type(exc).__name__}")
            return {"state": "error", "available": False, "reason": "consumer_presentation_unavailable", "error_type": type(exc).__name__, "cards": []}

        safe.render_wnba_daily_picks_hub = render_wnba_daily_picks_hub
        sys.modules["wnba_daily_picks_hub_v34"] = safe
        sys.modules["wnba_daily_picks_hub_v4"] = safe
        return {"installed": True, "fail_closed": True, "error_type": type(exc).__name__, "legacy_daily_picks_compute_fallback": False}


def _install_mlb_moneyline_step7c_route() -> dict:
    """Install only the V16.4 Moneyline presentation alias; fail open to V16.3."""
    for name in ("mlb_moneyline_hub_v164", "mlb_moneyline_hub_v163"):
        sys.modules.pop(name, None)
    importlib.invalidate_caches()
    try:
        import mlb_moneyline_hub_v164 as moneyline_v164

        prior = getattr(moneyline_v164, "prior", None)
        if prior is None or not hasattr(prior, "render_moneyline_hub"):
            raise RuntimeError("Moneyline V16.4 frozen V16.3 base failed to initialize.")
        sys.modules["mlb_moneyline_hub_v163"] = moneyline_v164
        return {
            "installed": True,
            "model_version": getattr(moneyline_v164, "MODEL_VERSION", "V16.4"),
            "frozen_v163_fallback_preserved": True,
        }
    except Exception as exc:
        sys.modules.pop("mlb_moneyline_hub_v164", None)
        sys.modules.pop("mlb_moneyline_hub_v163", None)
        importlib.invalidate_caches()
        import mlb_moneyline_hub_v163 as frozen_v163

        sys.modules["mlb_moneyline_hub_v163"] = frozen_v163
        return {
            "installed": False,
            "model_version": getattr(frozen_v163, "MODEL_VERSION", "V16.3"),
            "error_type": type(exc).__name__,
            "frozen_v163_fallback_preserved": True,
        }


def _install_mlb_totals_step7e_route() -> dict:
    """Install only the V17.4 Totals presentation alias; fail open to V17.3."""
    for name in ("mlb_totals_hub_v174", "mlb_totals_hub_v173"):
        sys.modules.pop(name, None)
    importlib.invalidate_caches()
    try:
        import mlb_totals_hub_v174 as totals_v174

        prior = getattr(totals_v174, "prior", None)
        if prior is None or not hasattr(prior, "render_totals_hub"):
            raise RuntimeError("Totals V17.4 frozen V17.3 base failed to initialize.")
        sys.modules["mlb_totals_hub_v173"] = totals_v174
        return {
            "installed": True,
            "model_version": getattr(totals_v174, "MODEL_VERSION", "V17.4"),
            "frozen_v173_fallback_preserved": True,
        }
    except Exception as exc:
        sys.modules.pop("mlb_totals_hub_v174", None)
        sys.modules.pop("mlb_totals_hub_v173", None)
        importlib.invalidate_caches()
        import mlb_totals_hub_v173 as frozen_v173

        sys.modules["mlb_totals_hub_v173"] = frozen_v173
        return {
            "installed": False,
            "model_version": getattr(frozen_v173, "MODEL_VERSION", "V17.3"),
            "error_type": type(exc).__name__,
            "frozen_v173_fallback_preserved": True,
        }


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


# Streamlit requires set_page_config to be the first UI command. The historical
# frozen shell owns that call, so install a narrow wrapper around the genuine
# function and add the new sidebar route only after page config succeeds.
_REAL_SET_PAGE_CONFIG = getattr(st, "_kyre_real_set_page_config", None)
if not callable(_REAL_SET_PAGE_CONFIG):
    _REAL_SET_PAGE_CONFIG = st.set_page_config
    setattr(st, "_kyre_real_set_page_config", _REAL_SET_PAGE_CONFIG)
_MLB_LIVE_ODDS_PAGE_CONFIG_HOOK_RAN = False


def _set_page_config_with_mlb_live_odds(*args, **kwargs):
    global _MLB_LIVE_ODDS_PAGE_CONFIG_HOOK_RAN
    result = _REAL_SET_PAGE_CONFIG(*args, **kwargs)
    if _MLB_LIVE_ODDS_PAGE_CONFIG_HOOK_RAN:
        return result
    _MLB_LIVE_ODDS_PAGE_CONFIG_HOOK_RAN = True

    if st.session_state.get("ks_mlb_live_odds_route") is True:
        from mlb_live_odds_streamlit_v1 import render_mlb_live_odds_page

        render_mlb_live_odds_page()
        st.stop()

    if st.sidebar.button(
        "⚾ MLB Live Odds",
        key="ks_mlb_live_odds_launch",
        use_container_width=True,
    ):
        st.session_state["ks_mlb_live_odds_route"] = True
        st.rerun()
    return result


st.set_page_config = _set_page_config_with_mlb_live_odds

_purge_live_runtime_state()
_refresh_pra_presentation_route()
_STEP7F_WNBA_API_BRIDGE = _install_step7f_wnba_api_bridge()
_STEP18C_WNBA_CONSUMER_BRIDGE = _install_step18c_wnba_consumer_bridge()
_STEP7C_MLB_MONEYLINE_ROUTE = _install_mlb_moneyline_step7c_route()
_STEP7E_MLB_TOTALS_ROUTE = _install_mlb_totals_step7e_route()
try:
    from mlb_step9c_live_state_consumer_v1 import install_step9c_live_state_consumer

    _STEP9C_MLB_LIVE_STATE_CONSUMER = install_step9c_live_state_consumer()
except Exception as exc:
    _STEP9C_MLB_LIVE_STATE_CONSUMER = {
        "installed": False,
        "error_type": type(exc).__name__,
        "legacy_direct_mlb_live_feed_preserved": True,
    }
try:
    from mlb_step9e_live_market_consumer_v1 import install_step9e_live_market_consumer

    _STEP9E_MLB_LIVE_MARKET_CONSUMER = install_step9e_live_market_consumer()
except Exception as exc:
    _STEP9E_MLB_LIVE_MARKET_CONSUMER = {
        "installed": False,
        "error_type": type(exc).__name__,
        "legacy_odds_api_io_fallback_preserved": True,
        "v1922_market_sync_function_preserved": True,
    }
source = _load_frozen_pre_live_app()

# Step 7B changes only the MLB Spread presentation import inside the frozen
# pre-live wrapper. The frozen wrapper still owns the historical V15.5 alias and
# clears V15.x modules before import, while this outer boundary clears V15.7 on
# every rerun so Streamlit cannot retain a stale API presentation wrapper.
_SPREAD_ROUTE_OLD = "    import mlb_spread_hub_v156 as spread_v156"
_SPREAD_ROUTE_NEW = "    import mlb_spread_hub_v157 as spread_v156"
if _SPREAD_ROUTE_OLD not in source:
    raise RuntimeError("Could not locate frozen MLB Spread V15.6 presentation seam.")
sys.modules.pop("mlb_spread_hub_v157", None)
importlib.invalidate_caches()
source = source.replace(_SPREAD_ROUTE_OLD, _SPREAD_ROUTE_NEW, 1)

# Step 8F installs only after the frozen pre-live shell has rebuilt the three
# current player-prop presentation chains. It patches final card renderers only;
# every projection/model/ranking function remains owned by the frozen modules.
_STEP8F_ROUTE_OLD = "_install_hrrbi_final_route()\n_install_mlb_spread_card_route()"
_STEP8F_ROUTE_NEW = (
    "_install_hrrbi_final_route()\n"
    "from mlb_step8f_player_prop_presentation_v1 import install_step8f_player_prop_presentation\n"
    "_STEP8F_MLB_PLAYER_PROP_PRESENTATION = install_step8f_player_prop_presentation()\n"
    "_install_mlb_spread_card_route()"
)
if _STEP8F_ROUTE_OLD not in source:
    raise RuntimeError("Could not locate frozen MLB Step 8F player-prop presentation seam.")
source = source.replace(_STEP8F_ROUTE_OLD, _STEP8F_ROUTE_NEW, 1)

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
