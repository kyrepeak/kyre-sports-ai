"""Universal Runtime V5 loader V12 — NFL tap-only + future-only navigation overlay.

All non-NFL destinations delegate unchanged to V11. Every NFL destination is
wrapped once so finite selectors are tap-only and schedule/game selectors only
surface verified future pregame matchups. No model or market math changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib

import universal_runtime_v5_loader_v11 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V12 • NFL FUTURE NAV"


def _wrap_nfl_adapter(adapter: DestinationAdapter) -> DestinationAdapter:
    def loader():
        return adapter.loader()

    def renderer(payload):
        import streamlit as st

        selector = importlib.import_module("universal_tap_only_selector_v2")
        future = importlib.import_module("nfl_universal_future_navigation_v1")
        nfl = importlib.import_module("nfl_hub_v1")

        original_loader = nfl.load_nfl_slate
        future_loader = future.make_future_only_loader(
            original_loader,
            now_provider=lambda: datetime.now(timezone.utc),
        )
        # Patch both module-qualified and direct-import aliases only for this NFL render.
        with future.install_future_only_nfl_loader(original_loader, future_loader):
            with selector.install_universal_tap_only_selectboxes():
                with future.install_nfl_future_selector_bridge(
                    st.session_state,
                    future_loader=future_loader,
                ):
                    return adapter.renderer(payload)

    return DestinationAdapter(
        adapter.route_key,
        loader,
        renderer,
        f"{adapter.source_version}+nfl-future-nav-v1",
        adapter.ttl_ms,
    )


def resolve_destination(route: RuntimeRoute):
    adapter = prior.resolve_destination(route)
    if route.sport_id == "nfl":
        return _wrap_nfl_adapter(adapter)
    return adapter


__all__ = [
    "MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch",
]
