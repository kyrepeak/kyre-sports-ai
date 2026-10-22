from __future__ import annotations

import importlib
from pathlib import Path


def test_actual_vercel_entrypoint_registers_nfl_passing_yards_router() -> None:
    entry = importlib.import_module("kyre_sports_api_vercel_v1")
    paths = {getattr(route, "path", "") for route in entry.nfl_passing_yards_page_router.routes}
    assert "/api/v1/nfl/passing-yards/page" in paths
    assert entry.nfl_passing_yards_page_router is not None
    health = entry.health()
    assert health.get("nfl_passing_yards_page") is True


def test_passing_yards_gateway_defaults_to_canonical_vercel_api() -> None:
    source = Path("nfl_passing_yards_gateway_v1.py").read_text(encoding="utf-8")
    assert 'DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"' in source
    assert "kyre-sports-api.onrender.com" not in source
