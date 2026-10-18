"""Universal Runtime V5 loader V13 — CFB tap-only + automatic next slate overlay."""
from __future__ import annotations

import importlib

import universal_runtime_v5_loader_v12 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V13 • CFB NEXT SLATE NAV"


def _wrap_cfb_adapter(adapter: DestinationAdapter) -> DestinationAdapter:
    def loader():
        return adapter.loader()

    def renderer(payload):
        import streamlit as st

        selector = importlib.import_module("universal_tap_only_selector_v2")
        nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")
        schedule = importlib.import_module("cfb_schedule_v1")
        resolved = nav.resolve_runtime_cfb_slate_date(games_loader=schedule.games_for_date)
        session_key = getattr(nav, "SESSION_DATE_KEY", "cfb_universal_next_slate_date")
        st.session_state[session_key] = resolved.isoformat() if resolved else ""
        with selector.install_universal_tap_only_selectboxes():
            with nav.install_cfb_next_slate_date_bridge(resolved):
                return adapter.renderer(payload)

    return DestinationAdapter(
        adapter.route_key,
        loader,
        renderer,
        f"{adapter.source_version}+cfb-next-slate-nav-v1",
        adapter.ttl_ms,
    )


def resolve_destination(route: RuntimeRoute):
    adapter = prior.resolve_destination(route)
    if route.sport_id == "cfb":
        return _wrap_cfb_adapter(adapter)
    return adapter


__all__ = [
    "MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch",
]
