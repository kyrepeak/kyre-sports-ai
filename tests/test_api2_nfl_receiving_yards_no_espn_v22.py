from __future__ import annotations

import importlib.util
from pathlib import Path

from api2_universal_sports_router_registry_v1 import get_router_registration, validate_router_registry

ROOT = Path(__file__).resolve().parents[1]
LIVE_FILES = (
    "nfl_receiving_yards_projection_v2.py",
    "nfl_receiving_yards_gateway_v2.py",
    "nfl_receiving_yards_hub_v22.py",
    "sports_api/collectors/nfl_fanduel_receiving_yards_nflverse_v2.py",
    "sports_api/api/nfl_receiving_yards_slate_v2.py",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_projection():
    path = ROOT / "nfl_receiving_yards_projection_v2.py"
    spec = importlib.util.spec_from_file_location("receiving_projection_v2_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v22_live_files_exist_and_are_free_of_legacy_source_dependency() -> None:
    for relative in LIVE_FILES:
        path = ROOT / relative
        assert path.exists(), f"missing live successor file: {relative}"
        source = path.read_text(encoding="utf-8").lower()
        assert "espn" not in source
        assert "sgo" not in source
        assert "espn bet" not in source


def test_registry_and_runtime_adapter_make_v22_the_only_live_page_owner() -> None:
    registration = get_router_registration("nfl", "receiving-yards")
    assert registration is not None
    assert registration.adapter_kind == "nfl-receiving-yards"
    assert registration.target == "nfl_receiving_yards_hub_v22"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.frontend_direct_provider is False
    loader = _read("universal_runtime_v5_loader.py")
    start = loader.index("def _nfl_receiving_yards_adapter")
    end = loader.index("\ndef ", start + 5)
    adapter = loader[start:end]
    assert '_import("nfl_receiving_yards_hub_v22")' in adapter
    assert "render_nfl_receiving_yards_hub()" in adapter
    assert "nfl_receiving_yards_hub_v21" not in adapter
    assert validate_router_registry() == ()


def test_frontend_v22_is_kyre_gateway_only() -> None:
    gateway = _read("nfl_receiving_yards_gateway_v2.py").lower()
    page = _read("nfl_receiving_yards_hub_v22.py").lower()
    assert "/api/v1/nfl/receiving-yards/slate-v2" in gateway
    assert "kyre_sports_api" in gateway
    assert "nfl_receiving_yards_gateway_v2" in page
    for forbidden in ("sportsbook.fanduel.com", "requests.get(", "urlopen(", "nfl_receiving_yards_hub_v21"):
        assert forbidden not in page
    assert "sportsbook_projection_influence = 0.0" in page


def test_vercel_mount_removes_legacy_receiving_routes_and_mounts_slate_v2() -> None:
    source = _read("kyre_sports_api_vercel_v1.py")
    assert "nfl_receiving_yards_slate_v2 as nfl_receiving_yards_slate_module" in source
    assert "app.include_router(nfl_receiving_yards_slate_router)" in source
    assert "sports_api.api.nfl_receiving_yards_context_v1" not in source
    assert "sports_api.api.nfl_receiving_yards_market_v1" not in source
    assert "app.include_router(nfl_receiving_yards_context_router)" not in source
    assert "app.include_router(nfl_receiving_yards_market_router)" not in source
    assert '"nfl_receiving_yards_slate_v2": True' in source


def test_universal_coverage_points_receiving_to_slate_v2() -> None:
    source = _read("sports_api/api/universal_sports_router_completion_v1.py")
    assert '("nfl", "receiving-yards"): "/api/v1/nfl/receiving-yards/slate-v2"' in source


def test_projection_v2_keeps_v1_math_and_market_isolation() -> None:
    projection = _load_projection()
    assert projection.EFFICIENCY_WEIGHTS == {
        "player_yards_per_reception": 0.65,
        "opponent_yards_per_reception_allowed": 0.35,
    }
    player = {
        "canonical_player_id": "kyre:nfl:player:00-TEST",
        "canonical_team_id": "kyre:nfl:team:ARI",
        "player_name": "Test Receiver",
        "position": "WR",
        "sample_games": 5,
        "receptions": 25,
        "receiving_yards": 300,
    }
    defense = {
        "canonical_team_id": "kyre:nfl:team:SEA",
        "yards_per_reception_allowed": 10.0,
    }
    result = projection.build_player_projection(
        canonical_game_id="kyre:nfl:game:2026_TEST",
        player=player,
        opponent_pass_defense=defense,
    )
    assert result["ready"] is True
    # 5 receptions/game * ((12 * .65) + (10 * .35)) = 56.5
    assert round(float(result["projection_yards"]), 6) == 56.5
    assert result["sportsbook_influence"] == 0.0
    assert result["market_used"] is False


def test_market_adapter_requires_exact_team_jersey_position_reconciliation() -> None:
    source = _read("sports_api/collectors/nfl_fanduel_receiving_yards_nflverse_v2.py")
    assert "PLAYER_NAME_MATCHING = False" in source
    assert "FUZZY_MATCHING = False" in source
    assert "team_abbr" in source
    assert "jersey_number" in source
    assert "position" in source
    assert "len(matches) != 1" in source
    assert "sportsbook_projection_influence" in source


def test_api_successor_uses_nflverse_fastpath_official_assets_and_upcoming_only() -> None:
    source = _read("sports_api/api/nfl_receiving_yards_slate_v2.py").lower()
    assert "nflverse" in source
    assert "stats_player_week" in source
    assert "receiving_yards" in source
    assert "opponent_team" in source
    assert "static.www.nfl.com" in source
    assert "kickoff <= now" in source
    assert "sportsbook_projection_influence" in source
    assert '"kyre sports api"' in source
