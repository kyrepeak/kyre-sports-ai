"""Runtime V5 loader V17 — CFB Moneyline V6 runtime-base repair override."""
from __future__ import annotations
import importlib
import universal_runtime_v5_loader_v16 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute
MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V17 • CFB MONEYLINE V6 RUNTIME BASE REPAIR"
DEFAULT_CFB_MONEYLINE_GATEWAY = "https://kyre-sports-api.vercel.app"
_MISSING_GATEWAY_ERROR = "Kyre Sports API gateway is not configured."


def _install_cfb_moneyline_gateway_binding(page):
    original_api_base = page._api_base

    def bound_api_base():
        try:
            return original_api_base()
        except RuntimeError as exc:
            if str(exc) != _MISSING_GATEWAY_ERROR:
                raise
            return DEFAULT_CFB_MONEYLINE_GATEWAY

    page._api_base = bound_api_base
    return original_api_base

def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "moneyline":
        base = prior.resolve_destination(route)
        def renderer(payload):
            selector = importlib.import_module("universal_tap_only_selector_v2")
            page = importlib.import_module("cfb_moneyline_clean_page_v6")  # frozen compatibility bootstrap
            page = importlib.import_module("cfb_moneyline_clean_page_v7")  # S-tier Kyre API successor
            original_api_base = _install_cfb_moneyline_gateway_binding(page)
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
                page._api_base = original_api_base
                page.st.caption = native_caption
        return DestinationAdapter(base.route_key, base.loader, renderer, MODEL_VERSION, base.ttl_ms)
    return prior.resolve_destination(route)

__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch"]
