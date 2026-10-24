"""Minimal Vercel entrypoint for the Kyre Sports API services."""
from __future__ import annotations

import sys
import types
from pathlib import Path

from fastapi import FastAPI
import sports_api as sports_api_pkg

_REPO_ROOT = Path(__file__).resolve().parent
# Avoid sports_api.api.__init__ because it owns unrelated historical bootstrap
# behavior. Expose only the real package path needed by the dedicated API routes.
_api_pkg = types.ModuleType("sports_api.api")
_api_pkg.__path__ = [str(_REPO_ROOT / "sports_api" / "api")]  # type: ignore[attr-defined]
_api_pkg.__package__ = "sports_api.api"
sys.modules.setdefault("sports_api.api", _api_pkg)
setattr(sports_api_pkg, "api", sys.modules["sports_api.api"])

import sports_api.api.cfb_moneyline_page1_v1 as cfb_moneyline_module
import sports_api.api.cfb_game_total_page1_v1 as cfb_game_total_module
import sports_api.api.cfb_top_picks_page1_v1 as cfb_top_picks_page1_module
import sports_api.api.cfb_top_picks_page1_v2 as cfb_top_picks_page1_v2_module
import sports_api.api.cfb_top_picks_page1_v3 as cfb_top_picks_page1_v3_module
import sports_api.api.cfb_top_picks_page1_v4 as cfb_top_picks_page1_v4_module
import sports_api.api.cfb_top_picks_page2_v1 as cfb_top_picks_page2_module
import sports_api.api.nfl_passing_yards_page_v1 as nfl_passing_yards_page_module
import sports_api.api.nfl_passing_yards_slate_v1 as nfl_passing_yards_slate_module
import sports_api.api.nfl_rushing_yards_slate_v1 as nfl_rushing_yards_slate_module
import sports_api.api.nfl_rushing_yards_detail_v2 as nfl_rushing_yards_detail_module
import sports_api.nfl_rushing_yards_fastpath_v1 as nfl_rushing_yards_fastpath

nfl_rushing_yards_fastpath.install(nfl_rushing_yards_slate_module)

cfb_moneyline_router = cfb_moneyline_module.router
cfb_game_total_router = cfb_game_total_module.router
cfb_top_picks_page1_router = cfb_top_picks_page1_module.router
cfb_top_picks_page1_v2_router = cfb_top_picks_page1_v2_module.router
cfb_top_picks_page1_v3_router = cfb_top_picks_page1_v3_module.router
cfb_top_picks_page1_v4_router = cfb_top_picks_page1_v4_module.router
cfb_top_picks_page2_router = cfb_top_picks_page2_module.router
nfl_passing_yards_page_router = nfl_passing_yards_page_module.router
nfl_passing_yards_slate_router = nfl_passing_yards_slate_module.router
nfl_rushing_yards_slate_router = nfl_rushing_yards_slate_module.router
nfl_rushing_yards_detail_router = nfl_rushing_yards_detail_module.router
app = FastAPI(
    title="Kyre Sports API",
    version="KYRE_GATEWAY_V8",
    description="Kyre Sports AI application-facing sports data gateway.",
)
app.include_router(cfb_moneyline_router)
app.include_router(cfb_game_total_router)
app.include_router(cfb_top_picks_page1_router)
app.include_router(cfb_top_picks_page1_v2_router)
app.include_router(cfb_top_picks_page1_v3_router)
app.include_router(cfb_top_picks_page1_v4_router)
app.include_router(cfb_top_picks_page2_router)
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
        "cfb_top_picks_page1": True,
        "cfb_top_picks_page1_v2": True,
        "cfb_top_picks_page1_v3": True,
        "cfb_top_picks_page1_v4": True,
        "cfb_top_picks_page2_v1": True,
        "nfl_passing_yards_page": True,
        "nfl_passing_yards_slate": True,
        "nfl_rushing_yards_slate": True,
        "nfl_rushing_yards_detail_v2": True,
        "direct_app_provider_fallback": False,
    }
