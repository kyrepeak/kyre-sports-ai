from __future__ import annotations

import json
from pathlib import Path

import cfb_player_props_model_v1 as frozen_model
import cfb_player_props_page2_v1 as page2
import universal_runtime_v5_loader_nfl_daily_picks_command_v3 as loader
from universal_runtime_v5_state import RuntimeRoute

ROOT = Path(__file__).resolve().parents[1]
FREEZE = "MONSTER_CFB_PLAYER_PROPS_PAGE2_V1_FROZEN"


def test_page2_runtime_is_single_canonical_lazy_destination_and_other_routes_stay_delegated(monkeypatch):
    route = RuntimeRoute("cfb", "player-props", {"date": "2026-10-24", "game_id": "401999001"}, 22, "tap")
    adapter = loader.resolve_destination(route)
    assert adapter.route_key == ("cfb", "player-props")
    assert adapter.source_version == "CFB_PLAYER_PROPS_RUNTIME_V3"
    assert adapter.ttl_ms == 30_000

    sentinel = object()
    seen = []
    monkeypatch.setattr(loader.upstream, "resolve_destination", lambda item: seen.append(item) or sentinel)
    other = RuntimeRoute("nfl", "spread", {}, 22, "tap")
    assert loader.resolve_destination(other) is sentinel
    assert seen == [other]


def test_page2_contract_remains_present_with_runtime_v3_successor_and_entrypoint_untouched():
    expected = {
        "cfb_player_props_runtime_v2.py",
        "cfb_player_props_page2_context_v1.py",
        "cfb_player_props_page2_roster_v1.py",
        "cfb_player_props_page2_availability_v1.py",
        "cfb_player_props_page2_market_v1.py",
        "cfb_player_props_page2_matchup_v1.py",
        "cfb_player_props_page2_handoff_v1.py",
        "cfb_player_props_page2_v1.py",
    }
    assert all((ROOT / name).exists() for name in expected)
    assert (ROOT / "cfb_player_props_runtime_v3.py").exists()
    assert "cfb_player_props" not in (ROOT / "app.py").read_text()


def test_frozen_projection_math_remains_book_independent_and_defense_is_presentation_only():
    assert frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    matchup_source = (ROOT / "cfb_player_props_page2_matchup_v1.py").read_text()
    assert "build_page1_signal" in matchup_source
    assert "build_prop_projection" in matchup_source
    assert "apply_to_raw" not in matchup_source


def test_runtime_overlay_does_not_introduce_nonselected_prefetch_or_duplicate_router():
    source = (ROOT / "universal_runtime_v5_loader_nfl_daily_picks_command_v3.py").read_text()
    assert "from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch" in source
    assert "def choose_prefetch" not in source
    assert "CFB_PLAYER_PROPS_RUNTIME_V3" in source


def test_control_plane_files_bind_exact_page2_freeze_token_and_runless_shapes():
    ledger_path = ROOT / "devsystem/task_ledgers/monster-cfb-player-props-page2-v1.json"
    proof_path = ROOT / "devsystem/runless_proof_plans/monster-cfb-player-props-page2-v1.json"
    assert ledger_path.exists()
    assert proof_path.exists()
    ledger = json.loads(ledger_path.read_text())
    proof = json.loads(proof_path.read_text())
    assert ledger["freeze_token"] == FREEZE
    assert proof["freeze_token"] == FREEZE
    assert proof["public_runtime_required"] is False
    assert proof["required_check"] == "runless-final-gate"
    assert proof["required_app_id"] == 5204253
    assert proof["sportsbook_projection_influence"] == 0.0
    assert all(command[:2] == ["python", "-m"] for command in proof["commands"])
    assert all(command[2] != "pip" for command in proof["commands"])
    assert any(command[2] == "py_compile" for command in proof["commands"])
    assert any(command[2] == "pytest" for command in proof["commands"])
    assert any(command[2] == "devsystem.api2_universal_runtime_v5_cert" for command in proof["commands"])
