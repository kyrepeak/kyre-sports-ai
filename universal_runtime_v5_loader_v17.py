"""Runtime V5 loader V17 — CFB Moneyline Premium V5 detail redesign override."""
from __future__ import annotations
import importlib
import universal_runtime_v5_loader_v16 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute
MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V17 • CFB MONEYLINE DETAIL REDESIGN V5"

def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "moneyline":
        base = prior.resolve_destination(route)
        def renderer(payload):
            import streamlit as st
            selector = importlib.import_module("universal_tap_only_selector_v2")
            nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")
            schedule = importlib.import_module("cfb_schedule_v1")
            page = importlib.import_module("cfb_moneyline_clean_page_v5")
            resolved = nav.resolve_runtime_cfb_slate_date(games_loader=schedule.games_for_date)
            session_key = getattr(nav, "SESSION_DATE_KEY", "cfb_universal_next_slate_date")
            st.session_state[session_key] = resolved.isoformat() if resolved else ""
            with selector.install_universal_tap_only_selectboxes():
                with nav.install_cfb_next_slate_date_bridge(resolved):
                    return page.render_moneyline_hub()
        return DestinationAdapter(base.route_key, base.loader, renderer, MODEL_VERSION, base.ttl_ms)
    return prior.resolve_destination(route)

__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch"]
