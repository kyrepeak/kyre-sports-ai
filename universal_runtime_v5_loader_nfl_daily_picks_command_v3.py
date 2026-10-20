"""Workstream-isolated Universal Runtime V5 overlay for NFL Daily Picks Command Center V3."""
from __future__ import annotations

import importlib

import universal_runtime_v5_loader_nba_spread_stier_v2 as upstream
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NFL DAILY PICKS COMMAND CENTER V3"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
BASE_LOADER_NAME = "universal_runtime_v5_loader_nba_spread_stier_v2"


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "player-props":
        def loader():
            return importlib.import_module("cfb_player_props_runtime_v3")

        def renderer(page):
            return page.render_cfb_player_props_runtime()

        return DestinationAdapter(
            ("cfb", "player-props"),
            loader,
            renderer,
            "CFB_PLAYER_PROPS_RUNTIME_V3",
            30_000,
        )
    if route.sport_id == "nfl" and route.market_id == "daily-picks":
        base_destination = upstream.resolve_destination(route)

        def loader():
            return importlib.import_module("nfl_daily_picks_command_center_v3")

        def renderer(page):
            return page.render_nfl_daily_picks_command_center()

        return DestinationAdapter(
            base_destination.route_key,
            loader,
            renderer,
            MODEL_VERSION,
            base_destination.ttl_ms,
        )
    return upstream.resolve_destination(route)


__all__ = [
    "BASE_LOADER_NAME",
    "DestinationAdapter",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "choose_prefetch",
    "load_destination",
    "resolve_destination",
    "run_prefetch",
]
