"""Additive Universal Runtime V5 overlay for NBA PRA Page 1 and CFB Game Total."""
from __future__ import annotations
import importlib
import universal_runtime_v5_loader_nfl_daily_picks_command_v4 as upstream
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute
MODEL_VERSION="API2 UNIVERSAL RUNTIME V5 • NBA PRA PAGE1 + CFB GAME TOTAL PAGE1 V1"
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
MAY_MODIFY_PROJECTION=False
BASE_LOADER_NAME="universal_runtime_v5_loader_nfl_daily_picks_command_v4"


def _cfb_game_total_destination(route: RuntimeRoute):
    base = upstream.resolve_destination(route)

    def loader():
        return (
            importlib.import_module("cfb_game_total_page1_stier_v1"),
            importlib.import_module("cfb_game_total_page2_market_completeness_r1"),
        )

    def renderer(bundle):
        import streamlit as st

        page1, page2 = bundle
        event_id = ""
        for key in ("game_id", "ks_cfb_game_total_event_id", "ks_cfb_game_total_selector_sync"):
            raw = st.query_params.get(key)
            if isinstance(raw, (list, tuple)):
                raw = raw[-1] if raw else ""
            event_id = str(raw or "").strip()
            if event_id:
                break
        if not event_id:
            event_id = str(st.session_state.get("ks_cfb_game_total_event_id") or "").strip()
        if event_id:
            return page2.render_cfb_hub("Game Total")
        return page1.render_cfb_hub("Game Total")

    return DestinationAdapter(
        base.route_key,
        loader,
        renderer,
        "cfb_game_total_page1_stier_v1+cfb_game_total_page2_market_completeness_r1",
        30_000,
    )


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "game-total":
        return _cfb_game_total_destination(route)
    if route.sport_id == "nba" and route.market_id == "pra":
        base=upstream.resolve_destination(route)
        def loader(): return importlib.import_module("nba_pra_page1_v1")
        def renderer(page): return page.render_nba_pra_page1()
        return DestinationAdapter(base.route_key,loader,renderer,MODEL_VERSION,30_000)
    return upstream.resolve_destination(route)
