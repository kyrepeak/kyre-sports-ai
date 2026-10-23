"""Universal Runtime V5 CFB Game Total API bootstrap repair R1."""
from __future__ import annotations

import importlib

import universal_runtime_v5_loader_nba_pra_page1_v1 as upstream
from universal_runtime_v5_loader import DestinationAdapter
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • CFB GAME TOTAL API BOOTSTRAP REPAIR R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def _cfb_game_total_destination(route: RuntimeRoute):
    base = upstream.resolve_destination(route)

    def loader():
        return (
            importlib.import_module("cfb_game_total_page1_api_bootstrap_repair_r1"),
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
        "cfb_game_total_page1_api_bootstrap_repair_r1+cfb_game_total_page2_market_completeness_r1",
        30_000,
    )


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "game-total":
        return _cfb_game_total_destination(route)
    return upstream.resolve_destination(route)


__all__ = ["MAY_MODIFY_PROJECTION", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "resolve_destination"]
