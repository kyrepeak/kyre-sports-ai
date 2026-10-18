"""WNBA PRA V3.6.15 — playoff-first customer product successor.

Presentation/orchestration successor over V3.6.14. The preserved PRA engine,
market grading, Monte Carlo, qualification, ranking, and selection math remain
owned by the predecessor stack; this module composes their read-only outputs.
"""
from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

import wnba_pra_hub_v3614 as previous
import wnba_pra_api_market_bridge_v1 as api_market
import wnba_pra_playoff_context_v1 as playoff
import wnba_pra_product_snapshot_v1 as snapshot
import wnba_pra_market_consensus_v1 as consensus
import wnba_pra_product_view_model_v1 as view_model
import wnba_pra_product_view_v1 as product

MODEL_VERSION = "PRA V3.6.15 • PLAYOFF PRODUCT V1 • MODEL PRESERVED"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH
STEP5_FROZEN_BASELINE = previous.STEP5_FROZEN_BASELINE
PRECISION_STEP1_CONTRACT = previous.PRECISION_STEP1_CONTRACT
PAGE_CLEANUP_CONTRACT = previous.PAGE_CLEANUP_CONTRACT
PLAYOFF_PRODUCT_CONTRACT = {
    "pra_first": True,
    "playoff_context": True,
    "multi_source": True,
    "multi_book_presentation": True,
    "advanced_diagnostics_collapsed": True,
    "projection_math_changed": False,
    "market_math_changed": False,
    "monte_carlo_changed": False,
    "qualification_changed": False,
    "ranking_changed": False,
    "selection_changed": False,
    "universal_runtime_v5_changed": False,
}


def _selected_date() -> str:
    key = "wnba_pra_v2_date"
    raw = st.session_state.get(key)
    if raw is not None:
        try:
            normalized = pd.to_datetime(raw).date()
        except Exception:
            normalized = pd.Timestamp.now(tz="America/New_York").date()
        st.session_state[key] = normalized
        selected = st.date_input("WNBA slate date", key=key)
    else:
        selected = st.date_input(
            "WNBA slate date",
            value=pd.Timestamp.now(tz="America/New_York").date(),
            key=key,
        )
    if isinstance(selected, tuple):
        selected = selected[0] if selected else date.today()
    return pd.to_datetime(selected).strftime("%Y-%m-%d")


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Keep the existing Kyre Sports API market ownership boundary first.
    api_market.install()
    selected_day = _selected_date()
    context = playoff.resolve_playoff_context(selected_day)
    product_snapshot = snapshot.build_product_snapshot(context.effective_date)
    market_consensus = consensus.build_market_consensus(product_snapshot.market_rows)
    player_views = view_model.build_player_views(product_snapshot, context, market_consensus)
    return product.render_pra_product(product_snapshot, context, player_views, market_consensus)


def __getattr__(name):
    return getattr(previous, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE", "PRECISION_STEP1_CONTRACT", "PAGE_CLEANUP_CONTRACT",
    "PLAYOFF_PRODUCT_CONTRACT", "render_wnba_pra_hub",
]
