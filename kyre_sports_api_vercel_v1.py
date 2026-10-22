"""Minimal Vercel entrypoint for the Kyre Sports API CFB services."""
from __future__ import annotations

import sys
import types
from pathlib import Path

from fastapi import FastAPI
import sports_api as sports_api_pkg

_REPO_ROOT = Path(__file__).resolve().parent
# Avoid sports_api.api.__init__ because it owns unrelated historical bootstrap
# behavior. Expose only the real package path needed by the dedicated CFB API.
_api_pkg = types.ModuleType("sports_api.api")
_api_pkg.__path__ = [str(_REPO_ROOT / "sports_api" / "api")]  # type: ignore[attr-defined]
_api_pkg.__package__ = "sports_api.api"
sys.modules.setdefault("sports_api.api", _api_pkg)
setattr(sports_api_pkg, "api", sys.modules["sports_api.api"])

import sports_api.api.cfb_moneyline_page1_v1 as cfb_moneyline_module
import sports_api.api.cfb_game_total_page1_v1 as cfb_game_total_module

cfb_moneyline_router = cfb_moneyline_module.router
cfb_game_total_router = cfb_game_total_module.router
app = FastAPI(
    title="Kyre Sports API",
    version="CFB_GATEWAY_V2",
    description="Kyre Sports AI application-facing sports data gateway.",
)
app.include_router(cfb_moneyline_router)
app.include_router(cfb_game_total_router)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "healthy",
        "service": "Kyre Sports API",
        "cfb_moneyline_page1": True,
        "cfb_game_total_page1": True,
        "direct_app_provider_fallback": False,
    }
