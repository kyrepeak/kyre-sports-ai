"""Runtime V5 loader V21 — CFB Game Total date/slate repair override."""
from __future__ import annotations

import importlib

import universal_runtime_v5_loader_v20 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V21 • CFB GAME TOTAL DATE + SLATE REPAIR V1"


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "game-total":
        base = prior.resolve_destination(route)

        def loader():
            return (
                importlib.import_module("cfb_game_total_page1_daily_slate_v1"),
                importlib.import_module("cfb_game_total_page2_market_completeness_r1"),
                importlib.import_module("cfb_game_total_v5_date_slate_repair_v1"),
            )

        def renderer(bundle):
            page1, page2, repair = bundle
            event_id = repair.selected_event_id(route)
            if event_id:
                repair.sync_selected_event_id(event_id, route)
                return page2.render_cfb_hub("Game Total")
            with repair.install_page1_runtime(page1):
                return page1.render_cfb_hub("Game Total")

        return DestinationAdapter(base.route_key, loader, renderer, MODEL_VERSION, base.ttl_ms)
    return prior.resolve_destination(route)


__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch"]
