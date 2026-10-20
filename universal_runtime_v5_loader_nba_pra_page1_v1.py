"""Additive Universal Runtime V5 overlay for NBA PRA Page 1."""
from __future__ import annotations
import importlib
import universal_runtime_v5_loader_nfl_daily_picks_command_v4 as upstream
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute
MODEL_VERSION="API2 UNIVERSAL RUNTIME V5 • NBA PRA PAGE1 V1"
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
MAY_MODIFY_PROJECTION=False
BASE_LOADER_NAME="universal_runtime_v5_loader_nfl_daily_picks_command_v4"
def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "nba" and route.market_id == "pra":
        base=upstream.resolve_destination(route)
        def loader(): return importlib.import_module("nba_pra_page1_v1")
        def renderer(page): return page.render_nba_pra_page1()
        return DestinationAdapter(base.route_key,loader,renderer,MODEL_VERSION,30_000)
    return upstream.resolve_destination(route)
