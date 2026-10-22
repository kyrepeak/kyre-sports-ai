"""Terminal overlay for adaptive CFB Top Picks Page 1 + Page 2 V1."""
from __future__ import annotations
import importlib
import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v4 as prior
from universal_runtime_v5_loader import DestinationAdapter

MODEL_VERSION="API2 UNIVERSAL RUNTIME V5 • CFB TOP PICKS PAGE2 ANALYTICS LAB V1"
MAY_MODIFY_PROJECTION=False
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
_prior_resolve_destination=prior.resolve_destination

def resolve_destination(route):
    if route.sport_id=="cfb" and route.market_id=="top-picks":
        base=_prior_resolve_destination(route)
        return DestinationAdapter(base.route_key,lambda:importlib.import_module("cfb_top_picks_page_v16"),lambda page:page.render_cfb_hub("Top Picks"),MODEL_VERSION,30_000)
    return _prior_resolve_destination(route)

frozen_runtime.resolve_destination=resolve_destination
record_bootstrap_import_ms=prior.record_bootstrap_import_ms
render_app=prior.render_app
__all__=["MODEL_VERSION","record_bootstrap_import_ms","render_app","resolve_destination"]
