"""Minimal Vercel entrypoint for the Kyre Sports API services."""
from __future__ import annotations

import sys
import types
from pathlib import Path

from fastapi import FastAPI

from sports_api.runtime.streamlit_api_compat_v1 import install_streamlit_api_compat

install_streamlit_api_compat()

import sports_api as sports_api_pkg

_REPO_ROOT = Path(__file__).resolve().parent
_api_pkg = types.ModuleType("sports_api.api")
_api_pkg.__path__ = [str(_REPO_ROOT / "sports_api" / "api")]  # type: ignore[attr-defined]
_api_pkg.__package__ = "sports_api.api"
sys.modules.setdefault("sports_api.api", _api_pkg)
setattr(sports_api_pkg, "api", sys.modules["sports_api.api"])

import sports_api.api.cfb_moneyline_page1_v1 as cfb_moneyline_module
import sports_api.api.cfb_game_total_page1_v1 as cfb_game_total_module
import sports_api.api.cfb_game_total_page1_decision_v1 as cfb_game_total_decision_module
import sports_api.api.cfb_top_picks_page1_v1 as cfb_top_picks_page1_module
import sports_api.api.cfb_top_picks_page1_v2 as cfb_top_picks_page1_v2_module
import sports_api.api.cfb_top_picks_page1_v3 as cfb_top_picks_page1_v3_module
import sports_api.api.cfb_top_picks_page1_v4 as cfb_top_picks_page1_v4_module
import sports_api.api.cfb_top_picks_page2_v1 as cfb_top_picks_page2_module
import sports_api.api.nba_gateway_v1 as nba_gateway_module
import sports_api.api.nba_pra_market_real_restore_v1 as nba_pra_market_module
import sports_api.api.nba_pra_schedule_v1 as nba_pra_schedule_module
import sports_api.api.nba_pra_player_context_v1 as nba_pra_player_context_module
import sports_api.api.nba_pra_player_context_completeness_v2 as nba_pra_player_context_completeness_module

nba_pra_player_context_completeness_module.install(nba_pra_player_context_module)

# Order is intentional: NBA Stats enriches the stable production route first;
# Basketball-Reference only fills usage fields that remain missing.
import sports_api.api.nba_pra_player_context_enrichment_v2 as nba_pra_player_context_enrichment_module  # noqa: F401,E402
import sports_api.api.nba_pra_usage_fallback_v2 as nba_pra_usage_fallback_module  # noqa: F401,E402
import sports_api.api.nba_pra_injury_v1 as nba_pra_injury_module
import sports_api.api.nba_pra_matchup_v1 as nba_pra_matchup_module
import sports_api.api.nfl_game_totals_page2_context_v2 as nfl_game_totals_page2_context_module
import sports_api.api.nfl_passing_yards_page_v1 as nfl_passing_yards_page_module
import sports_api.api.nfl_passing_yards_slate_v1 as nfl_passing_yards_slate_module
import sports_api.api.nfl_rushing_yards_slate_v1 as nfl_rushing_yards_slate_module
# Preserve the certified V3 import contract; V4 is the additive live successor.
import sports_api.api.nfl_rushing_yards_detail_v3 as nfl_rushing_yards_detail_module
import sports_api.api.nfl_rushing_yards_detail_v4 as nfl_rushing_yards_detail_v4_module
import sports_api.nfl_rushing_yards_fastpath_v1 as nfl_rushing_yards_fastpath

nfl_rushing_yards_fastpath.install(nfl_rushing_yards_slate_module)

cfb_moneyline_router = cfb_moneyline_module.router
cfb_game_total_router = cfb_game_total_module.router
cfb_game_total_decision_router = cfb_game_total_decision_module.router
cfb_top_picks_page1_router = cfb_top_picks_page1_module.router
cfb_top_picks_page1_v2_router = cfb_top_picks_page1_v2_module.router
cfb_top_picks_page1_v3_router = cfb_top_picks_page1_v3_module.router
cfb_top_picks_page1_v4_router = cfb_top_picks_page1_v4_module.router
cfb_top_picks_page2_router = cfb_top_picks_page2_module.router
nba_gateway_router = nba_gateway_module.router
nba_pra_market_router = nba_pra_market_module.router
nba_pra_schedule_router = nba_pra_schedule_module.router
nba_pra_player_context_router = nba_pra_player_context_module.router
nba_pra_injury_router = nba_pra_injury_module.router
nba_pra_matchup_router = nba_pra_matchup_module.router
nfl_game_totals_page2_context_router = nfl_game_totals_page2_context_module.router
nfl_passing_yards_page_router = nfl_passing_yards_page_module.router
nfl_passing_yards_slate_router = nfl_passing_yards_slate_module.router
nfl_rushing_yards_slate_router = nfl_rushing_yards_slate_module.router
nfl_rushing_yards_detail_router = nfl_rushing_yards_detail_v4_module.router

app = FastAPI(
    title="Kyre Sports API",
    version="KYRE_GATEWAY_V12",
    description="Kyre Sports AI application-facing sports data gateway.",
)
app.include_router(cfb_moneyline_router)
app.include_router(cfb_game_total_router)
app.include_router(cfb_game_total_decision_router)
app.include_router(cfb_top_picks_page1_router)
app.include_router(cfb_top_picks_page1_v2_router)
app.include_router(cfb_top_picks_page1_v3_router)
app.include_router(cfb_top_picks_page1_v4_router)
app.include_router(cfb_top_picks_page2_router)
app.include_router(nba_gateway_router)
app.include_router(nba_pra_market_router)
app.include_router(nba_pra_schedule_router)
app.include_router(nba_pra_player_context_router)
app.include_router(nba_pra_injury_router)
app.include_router(nba_pra_matchup_router)
app.include_router(nfl_game_totals_page2_context_router)
app.include_router(nfl_passing_yards_page_router)
app.include_router(nfl_passing_yards_slate_router)
app.include_router(nfl_rushing_yards_slate_router)
app.include_router(nfl_rushing_yards_detail_router)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "healthy",
        "service": "Kyre Sports API",
        "cfb_moneyline_page1": True,
        "cfb_game_total_page1": True,
        "cfb_game_total_page1_decision": True,
        "cfb_top_picks_page1": True,
        "cfb_top_picks_page1_v2": True,
        "cfb_top_picks_page1_v3": True,
        "cfb_top_picks_page1_v4": True,
        "cfb_top_picks_page2_v1": True,
        "nba_universal_gateway_v1": True,
        "nba_pra_market_provider_independence_v1": True,
        "nba_pra_market_real_restore_v1": True,
        "nba_pra_schedule_v1": True,
        "nba_pra_player_context_v1": True,
        "nba_pra_injury_v1": True,
        "nba_pra_matchup_v1": True,
        "nba_runless_product_transport": False,
        "nfl_game_totals_page2_context_v2": True,
        "nfl_passing_yards_page": True,
        "nfl_passing_yards_slate": True,
        "nfl_rushing_yards_slate": True,
        "nfl_rushing_yards_detail_v2": True,
        "nfl_rushing_yards_detail_v3": True,
        "nfl_rushing_yards_detail_v4": True,
        "direct_app_provider_fallback": False,
    }
