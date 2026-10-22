"""Runtime V5 loader V17 — CFB Moneyline V6 runtime-base repair override."""
from __future__ import annotations
import importlib
import universal_runtime_v5_loader_v16 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute
MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V17 • CFB MONEYLINE V6 RUNTIME BASE REPAIR"

def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "moneyline":
        base = prior.resolve_destination(route)
        def renderer(payload):
            selector = importlib.import_module("universal_tap_only_selector_v2")
            page = importlib.import_module("cfb_moneyline_clean_page_v6")  # frozen compatibility bootstrap
            page = importlib.import_module("cfb_moneyline_clean_page_v7")  # S-tier Kyre API successor
            native_caption = page.st.caption
            def normalized_caption(body, *args, **kwargs):
                if isinstance(body, str):
                    body = body.replace("price-indepent", "price-independent")
                return native_caption(body, *args, **kwargs)
            page.st.caption = normalized_caption
            try:
                with selector.install_universal_tap_only_selectboxes():
                    return page.render_moneyline_hub()
            finally:
                page.st.caption = native_caption
        return DestinationAdapter(base.route_key, base.loader, renderer, MODEL_VERSION, base.ttl_ms)
    return prior.resolve_destination(route)

__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch"]
