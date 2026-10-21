"""WNBA PRA V3.6.17 — Kyre API-only sportsbook routing successor."""
from __future__ import annotations

from datetime import datetime
import importlib
from zoneinfo import ZoneInfo

import wnba_pra_api_market_bridge_v2 as api_market
import wnba_pra_playoff_context_v1 as playoff

MODEL_VERSION = "PRA V3.6.17 • KYRE API-ONLY MARKET ROUTING • MODEL PRESERVED"
MLB_FROZEN_BASELINE = "6f439a251329c588a097abc9281f0a528c3053be"
MLB_FROZEN_BRANCH = "mlb-v217-frozen-20260818"
STEP5_FROZEN_BASELINE = {
    "behavior_version": "PRA V3.6.11",
    "production_route_commit": "b13c376583ab846fc55fec33595fe75463420d89",
    "v3611_hub_blob": "0d3c6883888a7613835cf44f2fb670364e2b9e20",
    "scope": "Step-5 presentation baseline + card-integrated opportunity audit",
    "model_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
}
PRECISION_STEP1_CONTRACT = {
    "name": "Opportunity Decomposition",
    "placement": "inside each V2.8 Top-5 player card after Projection Path",
    "read_only": True,
    "new_provider": False,
    "projection_input_changed": False,
    "sportsbook_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
}
PAGE_CLEANUP_CONTRACT = {
    "scope": "presentation_only",
    "hero_cleaned": True,
    "projection_math_changed": False,
    "market_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
}
PLAYOFF_PRODUCT_CONTRACT = {
    "pra_first": True,
    "playoff_context": True,
    "multi_source": True,
    "advanced_diagnostics_collapsed": True,
    "projection_math_changed": False,
    "market_math_changed": False,
    "ranking_changed": False,
    "selection_changed": False,
}
FANDUEL_PRODUCT_CONTRACT = {
    "historical_parent_contract": True,
    "kyre_api_market_transport": True,
    "sportsbook_projection_influence": 0.0,
    "projection_math_changed": False,
    "market_probability_math_changed": False,
    "ranking_changed": False,
    "selection_changed": False,
}
MULTISOURCE_PRODUCT_CONTRACT = {
    "application_gateway": "kyre_sports_api",
    "primary_market_provider": "fanduel",
    "secondary_market_provider": "draftkings",
    "secondary_only_when_primary_unusable": True,
    "provider_specific_quotes": True,
    "line_averaging": False,
    "sportsbook_projection_influence": 0.0,
    "projection_math_changed": False,
    "market_probability_math_changed": False,
    "monte_carlo_changed": False,
    "ranking_changed": False,
    "selection_changed": False,
}


def resolve_active_slate_date() -> str:
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    context = playoff.resolve_playoff_context(today)
    return context.effective_date


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Install the API-only market compatibility seam before importing the
    # preserved model modules that historically bind their market namespace at
    # import time. The historical provider implementation is never loaded here.
    token = api_market.install()
    try:
        snapshot = importlib.import_module("wnba_pra_product_snapshot_v1")
        consensus = importlib.import_module("wnba_pra_market_consensus_v1")
        view_model = importlib.import_module("wnba_pra_product_view_model_v1")
        product = importlib.import_module("wnba_pra_product_view_v3")

        selected_day = resolve_active_slate_date()
        context = playoff.resolve_playoff_context(selected_day)
        product_snapshot = snapshot.build_product_snapshot(context.effective_date)
        market_consensus = consensus.build_market_consensus(product_snapshot.market_rows)
        player_views = view_model.build_player_views(
            product_snapshot,
            context,
            market_consensus,
            require_fanduel=False,
        )
        return product.render_pra_product(product_snapshot, context, player_views, market_consensus)
    finally:
        api_market.restore(token)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE", "PRECISION_STEP1_CONTRACT", "PAGE_CLEANUP_CONTRACT",
    "PLAYOFF_PRODUCT_CONTRACT", "FANDUEL_PRODUCT_CONTRACT", "MULTISOURCE_PRODUCT_CONTRACT",
    "resolve_active_slate_date", "render_wnba_pra_hub",
]
