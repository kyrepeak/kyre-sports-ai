"""WNBA PRA V3.6.16 — FanDuel-qualified customer product successor.

The V3.6.15 playoff product, preserved projection engine, market grading,
Monte Carlo, qualification, ranking, and final selection remain authoritative.
This successor only requires an exact current FanDuel PRA offer before a player
can enter the primary customer board and renders the V2 customer surface.
"""
from __future__ import annotations

import wnba_pra_hub_v3615 as previous
import wnba_pra_api_market_bridge_v1 as api_market
import wnba_pra_playoff_context_v1 as playoff
import wnba_pra_product_snapshot_v1 as snapshot
import wnba_pra_market_consensus_v1 as consensus
import wnba_pra_product_view_model_v1 as view_model
import wnba_pra_product_view_v2 as product

MODEL_VERSION = "PRA V3.6.16 • FANDUEL PRODUCT V2 • MODEL PRESERVED"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH
STEP5_FROZEN_BASELINE = previous.STEP5_FROZEN_BASELINE
PRECISION_STEP1_CONTRACT = previous.PRECISION_STEP1_CONTRACT
PAGE_CLEANUP_CONTRACT = previous.PAGE_CLEANUP_CONTRACT
PLAYOFF_PRODUCT_CONTRACT = previous.PLAYOFF_PRODUCT_CONTRACT
FANDUEL_PRODUCT_CONTRACT = {
    "fanduel_primary_board_eligibility": True,
    "fanduel_displayed_threshold": True,
    "kyre_api_market_transport": True,
    "multi_source_context": True,
    "other_books_comparison_only": True,
    "sportsbook_projection_influence": 0.0,
    "projection_math_changed": False,
    "market_probability_math_changed": False,
    "monte_carlo_changed": False,
    "qualification_changed": False,
    "ranking_changed": False,
    "selection_changed": False,
    "universal_runtime_v5_changed": False,
}


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    api_market.install()
    selected_day = previous._selected_date()
    context = playoff.resolve_playoff_context(selected_day)
    product_snapshot = snapshot.build_product_snapshot(context.effective_date)
    market_consensus = consensus.build_market_consensus(product_snapshot.market_rows)
    player_views = view_model.build_player_views(
        product_snapshot,
        context,
        market_consensus,
        require_fanduel=True,
    )
    return product.render_pra_product(product_snapshot, context, player_views, market_consensus)


def __getattr__(name):
    return getattr(previous, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE", "PRECISION_STEP1_CONTRACT", "PAGE_CLEANUP_CONTRACT",
    "PLAYOFF_PRODUCT_CONTRACT", "FANDUEL_PRODUCT_CONTRACT", "render_wnba_pra_hub",
]
