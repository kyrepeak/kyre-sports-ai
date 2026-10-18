"""WNBA PRA V3.6.16 — FanDuel-qualified customer product successor."""
from __future__ import annotations

from datetime import datetime
import importlib
from zoneinfo import ZoneInfo

import wnba_pra_api_market_bridge_v1 as api_market
import wnba_pra_playoff_context_v1 as playoff
import wnba_pra_product_snapshot_v1 as snapshot
import wnba_pra_market_consensus_v1 as consensus
import wnba_pra_product_view_model_v1 as view_model
import wnba_pra_product_view_v2 as product

MODEL_VERSION = "PRA V3.6.16 • FANDUEL PRODUCT V2 • MODEL PRESERVED"
MLB_FROZEN_BASELINE = "6f439a251329c588a097abc9281f0a528c3053be"
MLB_FROZEN_BRANCH = "mlb-v217-frozen-20260818"
STEP5_FROZEN_BASELINE = {"behavior_version": "PRA V3.6.11", "production_route_commit": "b13c376583ab846fc55fec33595fe75463420d89", "v3611_hub_blob": "0d3c6883888a7613835cf44f2fb670364e2b9e20", "scope": "Step-5 presentation baseline + card-integrated opportunity audit", "model_math_changed": False, "ranking_changed": False, "qualification_changed": False, "monte_carlo_changed": False}
PRECISION_STEP1_CONTRACT = {"name": "Opportunity Decomposition", "placement": "inside each V2.8 Top-5 player card after Projection Path", "read_only": True, "new_provider": False, "projection_input_changed": False, "sportsbook_changed": False, "ranking_changed": False, "qualification_changed": False}
PAGE_CLEANUP_CONTRACT = {"scope": "presentation_only", "hero_cleaned": True, "off_day_zero_wall_removed": True, "raw_diagnostics_collapsed": True, "provider_secret_message_removed": True, "market_labels_user_facing": True, "matchup_labels_user_facing": True, "api_ownership_changed": False, "projection_math_changed": False, "market_math_changed": False, "ranking_changed": False, "qualification_changed": False, "monte_carlo_changed": False, "nfl_changed": False, "mlb_changed": False}
PLAYOFF_PRODUCT_CONTRACT = {"pra_first": True, "playoff_context": True, "multi_source": True, "multi_book_presentation": True, "advanced_diagnostics_collapsed": True, "projection_math_changed": False, "market_math_changed": False, "monte_carlo_changed": False, "qualification_changed": False, "ranking_changed": False, "selection_changed": False, "universal_runtime_v5_changed": False}
FANDUEL_PRODUCT_CONTRACT = {"fanduel_primary_board_eligibility": True, "fanduel_displayed_threshold": True, "kyre_api_market_transport": True, "multi_source_context": True, "other_books_comparison_only": True, "sportsbook_projection_influence": 0.0, "projection_math_changed": False, "market_probability_math_changed": False, "monte_carlo_changed": False, "qualification_changed": False, "ranking_changed": False, "selection_changed": False, "universal_runtime_v5_changed": False}


def resolve_active_slate_date() -> str:
    """Use today's verified WNBA slate, otherwise advance to the next verified game date."""
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    context = playoff.resolve_playoff_context(today)
    return context.effective_date


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    api_market.install()
    selected_day = resolve_active_slate_date()
    context = playoff.resolve_playoff_context(selected_day)
    product_snapshot = snapshot.build_product_snapshot(context.effective_date)
    market_consensus = consensus.build_market_consensus(product_snapshot.market_rows)
    player_views = view_model.build_player_views(product_snapshot, context, market_consensus, require_fanduel=True)
    return product.render_pra_product(product_snapshot, context, player_views, market_consensus)


def __getattr__(name):
    previous = importlib.import_module("wnba_pra_hub_v3615")
    return getattr(previous, name)


__all__ = ["MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "STEP5_FROZEN_BASELINE", "PRECISION_STEP1_CONTRACT", "PAGE_CLEANUP_CONTRACT", "PLAYOFF_PRODUCT_CONTRACT", "FANDUEL_PRODUCT_CONTRACT", "resolve_active_slate_date", "render_wnba_pra_hub"]
