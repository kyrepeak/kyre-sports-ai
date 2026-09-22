from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    SUPPORTED_CORE_MARKETS,
    build_market_provider_game_snapshot,
)
from sports_api.mlb_step12a_shadow_runtime_runner_v1 import shadow_runtime_manifest
from sports_api.mlb_step12b_live_runtime_assembly_v1 import (
    ASSEMBLY_STATUS as STEP12B_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP12B_MARKER,
    RUNTIME_MODE as STEP12B_MODE,
    assemble_live_runtime_shadow,
    live_runtime_assembly_manifest,
)
from sports_api.mlb_step12c_live_board_runtime_v1 import (
    BOARD_STATUS,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MLBStep12CLiveBoardRuntimeError,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    STEP12C_BASE_MAIN_SHA,
    build_live_board_runtime,
    live_board_runtime_manifest,
    validate_live_board_runtime,
)

BASE_SHA = "5257a82c08f8ceea893a77c7963bd1a82b4db72b"
ASSEMBLED = "2026-09-01T18:40:00Z"
EVALUATED = "2026-09-01T18:40:30Z"
STALE = "2026-09-01T18:30:00Z"
GAME1 = 778001
GAME2 = 778002


def _markets(prefix: str, *, total_line: float = 8.5, away_rl: float = 1.5):
    return {
        "moneyline": {
            "market_id": f"{prefix}-ml",
            "market_time_utc": None,
            "away_odds": 110,
            "home_odds": -130,
            "away_selection_id": f"{prefix}-mla",
            "home_selection_id": f"{prefix}-mlh",
        },
        "run_line": {
            "market_id": f"{prefix}-rl",
            "market_time_utc": None,
            "away_line": away_rl,
            "away_odds": -105,
            "home_line": -away_rl,
            "home_odds": -115,
            "away_selection_id": f"{prefix}-rla",
            "home_selection_id": f"{prefix}-rlh",
        },
        "total": {
            "market_id": f"{prefix}-tot",
            "market_time_utc": None,
            "line": total_line,
            "over_odds": -110,
            "under_odds": -110,
            "over_selection_id": f"{prefix}-o",
            "under_selection_id": f"{prefix}-u",
        },
    }


def _snapshot(
    provider: str,
    *,
    gamepk: int = GAME1,
    observed: str = ASSEMBLED,
    source_complete: bool = True,
    total_line: float = 8.5,
    away_rl: float = 1.5,
    phase: str = "PREGAME",
):
    name = {"fanduel": "FanDuel", "draftkings": "DraftKings"}[provider]
    prefix = ("fd" if provider == "fanduel" else "dk") + f"-{gamepk}-{phase.lower()}"
    return build_market_provider_game_snapshot(
        provider_key=provider,
        provider_name=name,
        provider_event_id=f"{prefix}-event",
        official_game_id=gamepk,
        observed_at_utc=observed,
        source_collected_at_utc=observed,
        market_phase=phase,
        transport="unit_test_fixture",
        source_payload_sha256=hashlib.sha256(
            f"{provider}-{gamepk}-{phase}-{observed}".encode()
        ).hexdigest(),
        markets=_markets(prefix, total_line=total_line, away_rl=away_rl),
        source_complete=source_complete,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )


def _game(gamepk: int, *, away: str = "Away Club", home: str = "Home Club"):
    return {
        "game_pk": gamepk,
        "game_date_utc": "2026-09-01T23:10:00Z",
        "status": "Scheduled",
        "venue": "Test Park",
        "away_team": away,
        "home_team": home,
        "away_probable_pitcher": None,
        "home_probable_pitcher": None,
    }


def _schedule(*games):
    rows = list(games or (_game(GAME1), _game(GAME2)))
    return {
        "source": "MLB Stats API",
        "date": "2026-09-01",
        "game_count": len(rows),
        "games": rows,
    }


def _assembly(snapshots=None, schedule=None, **kwargs):
    if snapshots is None:
        snapshots = [_snapshot("fanduel"), _snapshot("draftkings")]
    if schedule is None:
        schedule = _schedule()
    args = {
        "assembled_at_utc": ASSEMBLED,
        "evaluated_at_utc": EVALUATED,
        "step12a_manifest": shadow_runtime_manifest(),
    }
    args.update(kwargs)
    return assemble_live_runtime_shadow(schedule, snapshots, **args)


def _board(assembly=None):
    if assembly is None:
        assembly = _assembly()
    return build_live_board_runtime(
        assembly,
        step12b_manifest=live_runtime_assembly_manifest(),
    )


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step12c_live_board_runtime_v1"
    assert SCHEMA_VERSION == 1
    assert STEP12C_BASE_MAIN_SHA == BASE_SHA
    assert BOARD_STATUS == "STEP12C_LIVE_BOARD_RUNTIME_READY"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP12C_LIVE_BOARD_RUNTIME_GREEN"


def test_manifest_pins_step12b_exactly():
    manifest = live_board_runtime_manifest()
    assert manifest["step12c_base_main_sha"] == BASE_SHA
    assert manifest["step12b_assembly_status_required"] == STEP12B_STATUS
    assert manifest["step12b_runtime_mode_required"] == STEP12B_MODE
    assert manifest["step12b_final_certification_marker_required"] == STEP12B_MARKER


@pytest.mark.parametrize(
    "key",
    [
        "step12b_assembly_required",
        "step12b_assembly_revalidated",
        "deterministic_consumer_board",
        "exact_official_game_id_required",
        "market_row_identity_uses_exact_game_id_phase_market",
        "freshness_gate_preserved",
        "source_complete_gate_preserved",
        "same_line_gate_preserved",
        "observational_only",
        "future_controlled_runtime_activation_required",
    ],
)
def test_manifest_required_guards_are_true(key):
    assert live_board_runtime_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "actionable_output_enabled",
        "network_io_added_by_step12c",
        "live_secondary_provider_network_calls_enabled",
        "production_api_wiring_added_by_step12c",
        "production_runtime_wiring_added_by_step12c",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step12c",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "team_name_join_allowed",
        "player_name_join_allowed",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "live_board_as_model_input_allowed",
        "live_board_as_sportsbook_input_allowed",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ],
)
def test_manifest_protected_behaviors_are_false(key):
    assert live_board_runtime_manifest()[key] is False


def test_manifest_preserves_every_step9_protected_invariant():
    manifest = live_board_runtime_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_manifest_is_freshly_isolated():
    one = live_board_runtime_manifest()
    two = live_board_runtime_manifest()
    one["observational_only"] = False
    assert two["observational_only"] is True


def test_happy_path_board_is_valid():
    board = _board()
    assert validate_live_board_runtime(board) == {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_valid": True,
        "failures": [],
    }


def test_happy_path_board_identity_and_counts():
    board = _board()
    assert board["board_status"] == BOARD_STATUS
    assert board["runtime_mode"] == "SHADOW_ONLY"
    assert board["group_count"] == 1
    assert board["market_row_count"] == 3
    assert board["consensus_ready_market_count"] == 3
    assert board["shadow_failover_candidate_count"] == 0
    assert board["stale_provider_slot_count"] == 0
    assert board["exact_official_game_id_join_verified"] is True


def test_market_rows_use_exact_game_phase_market_identity():
    board = _board()
    assert board["row_keys"] == [
        f"{GAME1}:PREGAME:moneyline",
        f"{GAME1}:PREGAME:run_line",
        f"{GAME1}:PREGAME:total",
    ]
    assert len(set(board["row_keys"])) == board["market_row_count"]


@pytest.mark.parametrize("market_name", SUPPORTED_CORE_MARKETS)
def test_each_core_market_is_observational_not_actionable(market_name):
    row = next(row for row in _board()["market_rows"] if row["market_name"] == market_name)
    assert row["observational_only"] is True
    assert row["actionable"] is False
    assert row["best_price_selection_performed"] is False
    assert row["production_route_changed"] is False


@pytest.mark.parametrize("market_name", SUPPORTED_CORE_MARKETS)
def test_dual_provider_markets_show_consensus_ready(market_name):
    row = next(row for row in _board()["market_rows"] if row["market_name"] == market_name)
    assert row["provider_count"] == 2
    assert row["provider_keys"] == ["fanduel", "draftkings"]
    assert row["available_provider_count"] == 2
    assert row["available_provider_keys"] == ["fanduel", "draftkings"]
    assert row["shadow_route_provider"] == "fanduel"
    assert row["shadow_route_reason"] == "PRIMARY_AVAILABLE"
    assert row["shadow_failover_candidate"] is False
    assert row["consensus_available"] is True
    assert row["consensus_status"] == "TWO_PROVIDER_CONSENSUS_READY"
    assert row["consensus_provider_count"] == 2


def test_schedule_metadata_is_display_only_and_preserved():
    board = _board()
    metadata = board["groups"][0]["game_metadata"]
    assert metadata["away_team"] == "Away Club"
    assert metadata["home_team"] == "Home Club"
    assert metadata["venue"] == "Test Park"
    assert board["team_name_join_used"] is False
    assert board["player_name_join_used"] is False


def test_team_name_changes_do_not_change_exact_game_identity():
    board = _board(_assembly(schedule=_schedule(_game(GAME1, away="Renamed A", home="Renamed H"))))
    assert board["row_keys"] == [
        f"{GAME1}:PREGAME:moneyline",
        f"{GAME1}:PREGAME:run_line",
        f"{GAME1}:PREGAME:total",
    ]
    assert board["groups"][0]["game_metadata"]["away_team"] == "Renamed A"


def test_multiple_games_and_phases_are_deterministically_sorted():
    snapshots = [
        _snapshot("draftkings", gamepk=GAME2),
        _snapshot("fanduel", gamepk=GAME1, phase="IN_PLAY"),
        _snapshot("fanduel", gamepk=GAME2),
        _snapshot("draftkings", gamepk=GAME1, phase="IN_PLAY"),
    ]
    board = _board(_assembly(snapshots=snapshots))
    assert [
        (group["official_game_id"], group["market_phase"])
        for group in board["groups"]
    ] == [(GAME1, "IN_PLAY"), (GAME2, "PREGAME")]
    assert board["group_count"] == 2
    assert board["market_row_count"] == 6
    assert len(set(board["row_keys"])) == 6


def test_single_provider_board_remains_observational():
    board = _board(_assembly(snapshots=[_snapshot("fanduel")]))
    assert board["consensus_ready_market_count"] == 0
    assert board["shadow_failover_candidate_count"] == 0
    for row in board["market_rows"]:
        assert row["provider_count"] == 1
        assert row["consensus_available"] is False
        assert row["consensus_status"] == "INSUFFICIENT_PROVIDERS"
        assert row["shadow_route_provider"] == "fanduel"
        assert row["actionable"] is False


def test_stale_primary_creates_shadow_failover_candidates_only():
    assembly = _assembly(
        snapshots=[
            _snapshot("fanduel", observed=STALE),
            _snapshot("draftkings"),
        ],
        max_age_seconds=60,
    )
    board = _board(assembly)
    assert board["shadow_failover_candidate_count"] == 3
    assert board["stale_provider_slot_count"] == 1
    assert board["production_provider_failover_used"] is False
    for row in board["market_rows"]:
        assert row["shadow_route_provider"] == "draftkings"
        assert row["shadow_route_reason"] == "PRIMARY_UNAVAILABLE_FALLBACK_AVAILABLE"
        assert row["shadow_failover_candidate"] is True
        assert row["actionable"] is False
        assert row["production_route_changed"] is False


def test_incomplete_primary_creates_shadow_failover_candidates_only():
    assembly = _assembly(
        snapshots=[
            _snapshot("fanduel", source_complete=False),
            _snapshot("draftkings"),
        ]
    )
    board = _board(assembly)
    assert board["shadow_failover_candidate_count"] == 3
    for row in board["market_rows"]:
        assert row["shadow_route_provider"] == "draftkings"
        assert row["shadow_failover_candidate"] is True
        assert row["available_provider_keys"] == ["draftkings"]
        assert row["consensus_available"] is False


def test_total_line_mismatch_is_visible_but_not_actionable():
    assembly = _assembly(
        snapshots=[
            _snapshot("fanduel", total_line=8.5),
            _snapshot("draftkings", total_line=9.0),
        ]
    )
    board = _board(assembly)
    total = next(row for row in board["market_rows"] if row["market_name"] == "total")
    assert total["consensus_available"] is False
    assert total["consensus_status"] == "LINE_MISMATCH"
    assert total["consensus"] is None
    assert total["actionable"] is False
    assert board["consensus_ready_market_count"] == 2


def test_run_line_mismatch_is_visible_but_not_actionable():
    assembly = _assembly(
        snapshots=[
            _snapshot("fanduel", away_rl=1.5),
            _snapshot("draftkings", away_rl=2.5),
        ]
    )
    board = _board(assembly)
    run_line = next(row for row in board["market_rows"] if row["market_name"] == "run_line")
    assert run_line["consensus_available"] is False
    assert run_line["consensus_status"] == "LINE_MISMATCH"
    assert run_line["actionable"] is False
    assert board["consensus_ready_market_count"] == 2


@pytest.mark.parametrize(
    "key,expected",
    [
        ("network_io_performed", False),
        ("live_secondary_provider_network_calls", 0),
        ("production_api_wiring", False),
        ("production_runtime_wiring", False),
        ("production_provider_consensus_used", False),
        ("production_provider_failover_used", False),
        ("best_price_selection_used", False),
        ("provider_weighting_used", False),
        ("production_database_writes", 0),
        ("persistence_schema_changed", False),
        ("price_fabrication_used", False),
        ("fallback_price_fabrication_used", False),
        ("team_name_join_used", False),
        ("player_name_join_used", False),
        ("fuzzy_matching_used", False),
        ("synthetic_game_id_used", False),
        ("live_board_as_model_input", False),
        ("live_board_as_sportsbook_input", False),
        ("persisted_snapshot_as_model_input", False),
        ("persisted_snapshot_as_sportsbook_input", False),
    ],
)
def test_runtime_protected_outputs_remain_disabled(key, expected):
    assert _board()[key] == expected


def test_board_carries_exact_source_assembly_hash():
    assembly = _assembly()
    board = _board(assembly)
    assert board["source_assembly_sha256"] == assembly["assembly_sha256"]
    assert board["source_assembly"] == assembly


def test_builder_is_deterministic():
    assembly = _assembly()
    first = _board(assembly)
    second = _board(deepcopy(assembly))
    assert first == second
    assert first["board_sha256"] == second["board_sha256"]


def test_input_assembly_is_not_mutated():
    assembly = _assembly()
    before = deepcopy(assembly)
    _board(assembly)
    assert assembly == before


def test_output_is_deep_copy_isolated_from_input():
    assembly = _assembly()
    board = _board(assembly)
    board["source_assembly"]["official_schedule"]["games"][0]["away_team"] = "Mutated"
    assert assembly["official_schedule"]["games"][0]["away_team"] == "Away Club"


def test_nested_market_rows_are_deep_copy_isolated():
    board = _board()
    board["groups"][0]["markets"][0]["provider_observations"][0]["market"]["away_odds"] = 999
    assert board["market_rows"][0]["provider_observations"][0]["market"]["away_odds"] == 110


def test_non_mapping_manifest_fails_closed():
    with pytest.raises(MLBStep12CLiveBoardRuntimeError, match="step12b_manifest must be a mapping"):
        build_live_board_runtime(_assembly(), step12b_manifest=None)


def test_tampered_manifest_fails_closed():
    manifest = live_runtime_assembly_manifest()
    manifest["runtime_mode"] = "LIVE"
    with pytest.raises(MLBStep12CLiveBoardRuntimeError, match="manifest mismatch"):
        build_live_board_runtime(_assembly(), step12b_manifest=manifest)


def test_non_mapping_assembly_fails_closed():
    with pytest.raises(MLBStep12CLiveBoardRuntimeError, match="source_assembly must be a mapping"):
        build_live_board_runtime(None, step12b_manifest=live_runtime_assembly_manifest())


def test_tampered_step12b_assembly_fails_closed():
    assembly = _assembly()
    assembly["official_game_ids"] = [999999]
    with pytest.raises(MLBStep12CLiveBoardRuntimeError, match="validation failed"):
        _board(assembly)


@pytest.mark.parametrize("value", [None, 1, "bad", [], True])
def test_validator_rejects_non_mapping_values(value):
    result = validate_live_board_runtime(value)
    assert result["board_valid"] is False
    assert result["failures"] == ["STEP12C_BOARD_NOT_MAPPING"]


@pytest.mark.parametrize(
    "path,value",
    [
        ("board_status", "BAD"),
        ("runtime_mode", "LIVE"),
        ("market_row_count", 999),
        ("consensus_ready_market_count", 999),
        ("production_runtime_wiring", True),
        ("production_provider_consensus_used", True),
        ("production_provider_failover_used", True),
        ("price_fabrication_used", True),
        ("fuzzy_matching_used", True),
        ("synthetic_game_id_used", True),
        ("board_sha256", "0" * 64),
    ],
)
def test_validator_rejects_top_level_tampering(path, value):
    board = _board()
    board[path] = value
    result = validate_live_board_runtime(board)
    assert result["board_valid"] is False
    assert "STEP12C_BOARD_EXACT_CONTRACT_MISMATCH" in result["failures"]


def test_validator_rejects_market_row_tampering():
    board = _board()
    board["market_rows"][0]["actionable"] = True
    result = validate_live_board_runtime(board)
    assert result["board_valid"] is False
    assert "STEP12C_BOARD_EXACT_CONTRACT_MISMATCH" in result["failures"]


def test_validator_rejects_source_assembly_tampering():
    board = _board()
    board["source_assembly"]["production_runtime_wiring"] = True
    result = validate_live_board_runtime(board)
    assert result["board_valid"] is False
    assert result["failures"][0].startswith("STEP12C_REBUILD_FAILED:")


def test_validator_does_not_mutate_board():
    board = _board()
    before = deepcopy(board)
    validate_live_board_runtime(board)
    assert board == before


def test_hash_changes_when_observational_source_changes():
    first = _board(_assembly(schedule=_schedule(_game(GAME1, away="Club A"))))
    second = _board(_assembly(schedule=_schedule(_game(GAME1, away="Club B"))))
    assert first["board_sha256"] != second["board_sha256"]
    assert first["row_keys"] == second["row_keys"]


def test_two_game_board_keeps_unmatched_schedule_game_out_of_market_rows():
    board = _board(_assembly())
    assert GAME2 in board["source_assembly"]["unmatched_official_game_ids"]
    assert all(row["official_game_id"] == GAME1 for row in board["market_rows"])


def test_final_board_never_becomes_actionable_from_consensus_readiness():
    board = _board()
    assert board["consensus_ready_market_count"] == 3
    assert board["observational_only"] is True
    assert board["actionable_output"] is False
    assert all(row["actionable"] is False for row in board["market_rows"])
