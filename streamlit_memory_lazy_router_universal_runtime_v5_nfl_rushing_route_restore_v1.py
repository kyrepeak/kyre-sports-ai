"""Terminal successor restoring NBA PRA, NFL Rushing and CFB Moneyline rail ownership.

This overlay preserves the current CFB Game Total bootstrap terminal, restores
NBA / PRA and NFL / Rushing Yards as before, and shadows only CFB / Moneyline
presentation to the V8 compact logo rail. Model/projection behavior is not
modified.
"""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1 as prior
import universal_runtime_v5_loader as canonical_loader
from universal_page_experience_runtime_v5 import render_page_experience_app_v5
from universal_runtime_v5_loader import DestinationAdapter

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NBA PRA + NFL RUSHING + CFB MONEYLINE LOGO RAIL R1"
FROZEN_RUNTIME = prior.FROZEN_RUNTIME
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime = prior.frozen_runtime
_prior_resolve_destination = prior.resolve_destination


def resolve_destination(route):
    """Shadow only approved successor routes while preserving every other terminal route."""
    if route.sport_id == "cfb" and route.market_id == "moneyline":
        base = _prior_resolve_destination(route)

        def loader():
            return importlib.import_module("cfb_moneyline_clean_page_v8")

        def renderer(page):
            gateway = importlib.import_module("universal_runtime_v5_loader_v17")
            original_api_base = gateway._install_cfb_moneyline_gateway_binding(page)
            native_caption = page.st.caption

            def normalized_caption(body, *args, **kwargs):
                if isinstance(body, str):
                    body = body.replace("price-indepent", "price-independent")
                return native_caption(body, *args, **kwargs)

            page.st.caption = normalized_caption
            try:
                return page.render_moneyline_hub()
            finally:
                page._api_base = original_api_base
                page.st.caption = native_caption

        return DestinationAdapter(
            base.route_key,
            loader,
            renderer,
            "cfb_moneyline_clean_page_v8_logo_rail_r1",
            base.ttl_ms,
        )
    if route.sport_id == "nba" and route.market_id == "pra":
        def loader():
            return importlib.import_module("nba_pra_runtime_v2")

        def renderer(page):
            return page.render_nba_pra_runtime_v2()

        return DestinationAdapter(
            (route.sport_id, route.market_id),
            loader,
            renderer,
            "nba_pra_runtime_v2_api_only_terminal_restore_r1",
            30_000,
        )
    if route.sport_id == "nfl" and route.market_id == "rushing-yards":
        return canonical_loader.resolve_destination(route)
    return _prior_resolve_destination(route)


frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_page_experience_app_v5(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
