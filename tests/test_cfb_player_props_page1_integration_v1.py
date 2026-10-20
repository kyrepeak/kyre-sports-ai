from __future__ import annotations

from pathlib import Path

import cfb_player_props_model_v1 as model
import cfb_player_props_page1_slate_v1 as slate
import universal_runtime_v5_loader_nfl_daily_picks_command_v3 as loader
from universal_runtime_v5_state import RuntimeRoute

ROOT = Path(__file__).resolve().parents[1]


def test_player_props_route_is_single_lazy_runtime_destination_and_nonselected_delegates(monkeypatch):
    route = RuntimeRoute("cfb", "player-props", {"date": "2026-10-24"}, 4, "tap")
    adapter = loader.resolve_destination(route)
    assert adapter.route_key == ("cfb", "player-props")
    assert adapter.source_version == "CFB_PLAYER_PROPS_RUNTIME_V2"

    seen = []
    sentinel = object()
    monkeypatch.setattr(loader.upstream, "resolve_destination", lambda r: seen.append(r) or sentinel)
    other = RuntimeRoute("cfb", "moneyline", {}, 4, "tap")
    assert loader.resolve_destination(other) is sentinel
    assert seen == [other]


def test_page1_reuses_next_slate_rules_with_current_schedule_owner_and_projection_is_book_independent():
    source = (ROOT / "cfb_player_props_page1_slate_v1.py").read_text()
    assert "cfb_universal_next_slate_navigation_v1 as next_slate" in source
    assert "import cfb_schedule_v4 as schedule" in source
    assert "next_slate.game_is_future_pregame" in source
    assert model.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_scope_adds_only_page2_while_entrypoint_stays_untouched():
    names = {path.name for path in ROOT.glob("cfb_player_props_page*_v1.py")}
    assert "cfb_player_props_page1_v1.py" in names
    assert "cfb_player_props_page2_v1.py" in names
    assert "cfb_player_props_page3_v1.py" not in names
    app = (ROOT / "app.py").read_text()
    assert "cfb_player_props" not in app


def test_handoff_contract_uses_exact_official_game_id():
    import cfb_player_props_page1_handoff_v1 as handoff
    from datetime import date

    payload = handoff.build_selected_game_handoff(
        {
            "official_game_id": "401999001", "away_team_id": "101", "away_team": "Away",
            "home_team_id": "202", "home_team": "Home", "kickoff_iso": "2026-10-24T19:30:00-04:00",
        },
        slate_date=date(2026, 10, 24), generation=12,
    )
    assert payload["official_game_id"] == "401999001"
    assert payload["market_id"] == "player-props"
    assert payload["generation"] == 12


def test_page1_control_plane_artifacts_stay_bound_to_frozen_token():
    ledger = ROOT / "devsystem/task_ledgers/monster-cfb-player-props-page1-v1.json"
    proof = ROOT / "devsystem/runless_proof_plans/monster-cfb-player-props-page1-v1.json"
    assert ledger.exists()
    assert proof.exists()
    assert "MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN" in ledger.read_text()
    assert "MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN" in proof.read_text()
