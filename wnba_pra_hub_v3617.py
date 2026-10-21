"""WNBA PRA V3.6.17 — maximum-speed snapshot-first successor."""
from __future__ import annotations

from datetime import date, datetime
import importlib
import os
import socket
from zoneinfo import ZoneInfo

from wnba_pra_page_snapshot_client_v1 import WNBAPRASnapshotClientError, fetch_page_snapshot
from wnba_pra_page_snapshot_publish_v1 import WNBAPRASnapshotPublishError, refresh_if_claimed
from wnba_pra_page_snapshot_renderer_v1 import render_page_snapshot

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
    "name": "Opportunity Decomposition", "placement": "inside each V2.8 Top-5 player card after Projection Path",
    "read_only": True, "new_provider": False, "projection_input_changed": False, "sportsbook_changed": False,
    "ranking_changed": False, "qualification_changed": False,
}
PAGE_CLEANUP_CONTRACT = {
    "scope": "presentation_only", "hero_cleaned": True, "projection_math_changed": False,
    "market_math_changed": False, "ranking_changed": False, "qualification_changed": False,
}
PLAYOFF_PRODUCT_CONTRACT = {
    "pra_first": True, "playoff_context": True, "multi_source": True, "advanced_diagnostics_collapsed": True,
    "projection_math_changed": False, "market_math_changed": False, "ranking_changed": False, "selection_changed": False,
}
FANDUEL_PRODUCT_CONTRACT = {
    "historical_parent_contract": True, "kyre_api_market_transport": True, "sportsbook_projection_influence": 0.0,
    "projection_math_changed": False, "market_probability_math_changed": False, "ranking_changed": False,
    "qualification_changed": False, "selection_changed": False,
}
MULTISOURCE_PRODUCT_CONTRACT = {
    "application_gateway": "kyre_sports_api", "primary_market_provider": "fanduel",
    "secondary_market_provider": "draftkings", "secondary_only_when_primary_unusable": True,
    "provider_specific_quotes": True, "line_averaging": False, "sportsbook_projection_influence": 0.0,
    "projection_math_changed": False, "market_probability_math_changed": False, "monte_carlo_changed": False,
    "ranking_changed": False, "selection_changed": False,
}
_REFRESH_OWNER = f"streamlit-{socket.gethostname()}-{os.getpid()}"


def resolve_active_slate_date() -> str:
    try:
        import streamlit as st
        selected = st.session_state.get("wnba_pra_v2_date")
        if selected:
            if isinstance(selected, (date, datetime)):
                return selected.date().isoformat() if isinstance(selected, datetime) else selected.isoformat()
            return datetime.fromisoformat(str(selected)).date().isoformat()
    except Exception:
        pass
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def _refresh(day: str, *, background: bool) -> bool:
    return refresh_if_claimed(day, season=2026, owner_id=_REFRESH_OWNER, background=background)


def _render_degraded(day: str, section_header=None, status_info=None, team_logo=None, h=None):
    """Preserved heavy renderer, imported only after snapshot transport failure."""
    api_market = importlib.import_module("wnba_pra_api_market_bridge_v2")
    playoff = importlib.import_module("wnba_pra_playoff_context_v1")
    token = api_market.install()
    try:
        snapshot = importlib.import_module("wnba_pra_product_snapshot_v1")
        consensus = importlib.import_module("wnba_pra_market_consensus_v1")
        view_model = importlib.import_module("wnba_pra_product_view_model_v1")
        product = importlib.import_module("wnba_pra_product_view_v3")
        context = playoff.resolve_playoff_context(day)
        product_snapshot = snapshot.build_product_snapshot(context.effective_date)
        market_consensus = consensus.build_market_consensus(product_snapshot.market_rows)
        player_views = view_model.build_player_views(product_snapshot, context, market_consensus, require_fanduel=False)
        product.render_pra_product(product_snapshot, context, player_views, market_consensus)
        return {"snapshot_state": "DEGRADED_LEGACY", "date": context.effective_date}
    finally:
        api_market.restore(token)


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = resolve_active_slate_date()
    try:
        payload = fetch_page_snapshot(day, season=2026)
    except WNBAPRASnapshotClientError:
        return _render_degraded(day, section_header, status_info, team_logo, h)

    state = str(payload.get("snapshot_state") or "MODEL_UNAVAILABLE")
    cache = str(payload.get("cache_state") or "MODEL_UNAVAILABLE")

    if state == "MODEL_UNAVAILABLE":
        try:
            import streamlit as st
            st.warning("WNBA PRA model artifact is rebuilding through the certified Kyre data path.")
        except Exception:
            pass
        try:
            if _refresh(day, background=False):
                payload = fetch_page_snapshot(day, season=2026)
                render_page_snapshot(payload, section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)
                return payload
        except (WNBAPRASnapshotPublishError, WNBAPRASnapshotClientError):
            return _render_degraded(day, section_header, status_info, team_logo, h)
        render_page_snapshot(payload, section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)
        return payload

    render_page_snapshot(payload, section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)
    if payload.get("refresh_required") is True or cache == "STALE_SAFE" or state == "MODEL_REFRESH_REQUIRED":
        try:
            _refresh(day, background=True)
        except WNBAPRASnapshotPublishError:
            pass
    return payload


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "STEP5_FROZEN_BASELINE",
    "PRECISION_STEP1_CONTRACT", "PAGE_CLEANUP_CONTRACT", "PLAYOFF_PRODUCT_CONTRACT",
    "FANDUEL_PRODUCT_CONTRACT", "MULTISOURCE_PRODUCT_CONTRACT", "resolve_active_slate_date", "render_wnba_pra_hub",
]
