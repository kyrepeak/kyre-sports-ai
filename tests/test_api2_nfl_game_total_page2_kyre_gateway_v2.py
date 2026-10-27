from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types


def _load_api_module():
    import sports_api as sports_api_pkg
    root = Path(__file__).resolve().parents[1]
    api_pkg = types.ModuleType("sports_api.api")
    api_pkg.__path__ = [str(root / "sports_api" / "api")]  # type: ignore[attr-defined]
    api_pkg.__package__ = "sports_api.api"
    sys.modules["sports_api.api"] = api_pkg
    setattr(sports_api_pkg, "api", api_pkg)
    sys.modules.pop("sports_api.api.nfl_game_totals_page2_context_v2", None)
    return importlib.import_module("sports_api.api.nfl_game_totals_page2_context_v2")


def test_streamlit_page2_uses_only_kyre_sports_api_gateway_for_new_context():
    page = Path("nfl_game_totals_hub_v12.py").read_text(encoding="utf-8")
    context = Path("nfl_game_totals_page2_context_v2.py").read_text(encoding="utf-8")
    assert "nfl_game_totals_page2_context_v2" in page
    assert "nfl_game_totals_page2_context_gateway_v2" in context
    assert "sports_api import nfl_data_nflverse_v1" not in context
    assert "NFL_INJURY_URL" not in context
    assert "requests.get" not in context
    assert "load_matchup_history" in page
    assert "load_availability" in page


def test_gateway_targets_owned_page2_context_endpoint_and_fails_closed():
    gateway = importlib.import_module("nfl_game_totals_page2_context_gateway_v2")
    assert gateway.SCHEMA_VERSION == "nfl_game_totals_page2_context_v2"
    assert gateway.ENDPOINT_PATH == "/api/v1/nfl/game-totals/page2-context"
    failed = gateway.validate_page2_context_payload({}, away_abbr="DAL", home_abbr="PHI")
    assert failed["ready"] is False
    assert failed["history"]["ready"] is False
    assert failed["availability"]["ready"] is False


def test_kyre_sports_api_registers_game_total_page2_context_router():
    source = Path("kyre_sports_api_vercel_v1.py").read_text(encoding="utf-8")
    assert "sports_api.api.nfl_game_totals_page2_context_v2" in source
    assert "nfl_game_totals_page2_context_router" in source
    assert "app.include_router(nfl_game_totals_page2_context_router)" in source


def test_api_context_contract_keeps_new_context_display_only():
    api = _load_api_module()
    payload = api.build_page2_context(away_abbr="DAL", home_abbr="PHI", history_frame=None, injury_html="")
    assert payload["schema_version"] == "nfl_game_totals_page2_context_v2"
    assert payload["gateway"] == "KYRE_SPORTS_API"
    assert payload["identity"] == {"away_abbr": "DAL", "home_abbr": "PHI"}
    assert payload["semantics"]["history_model_influence"] == 0.0
    assert payload["semantics"]["availability_model_influence"] == 0.0
    assert payload["semantics"]["stake_sizing_enabled"] is False
    assert payload["semantics"]["wager_actions"] is False
