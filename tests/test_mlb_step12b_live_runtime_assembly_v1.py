from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import build_market_provider_game_snapshot
from sports_api.mlb_step12a_shadow_runtime_runner_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12A_MARKER,
    RUNTIME_MODE as STEP12A_MODE,
    RUNTIME_STATUS as STEP12A_STATUS,
    shadow_runtime_manifest,
)
from sports_api.mlb_step12b_live_runtime_assembly_v1 import (
    ASSEMBLY_STATUS,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MAX_OFFICIAL_GAMES,
    MLBStep12BLiveRuntimeAssemblyError,
    OFFICIAL_SCHEDULE_SOURCE,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    STEP12B_BASE_MAIN_SHA,
    assemble_live_runtime_shadow,
    live_runtime_assembly_manifest,
    validate_live_runtime_assembly,
)

BASE_SHA = "886a839dab28a7da3c5a0d597d500d568c4a60fb"
ASSEMBLED = "2026-09-01T18:20:00Z"
EVALUATED = "2026-09-01T18:20:30Z"
GAME1 = 777001
GAME2 = 777002


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
):
    name = {"fanduel": "FanDuel", "draftkings": "DraftKings"}[provider]
    prefix = ("fd" if provider == "fanduel" else "dk") + f"-{gamepk}"
    return build_market_provider_game_snapshot(
        provider_key=provider,
        provider_name=name,
        provider_event_id=f"{prefix}-event",
        official_game_id=gamepk,
        observed_at_utc=observed,
        source_collected_at_utc=observed,
        market_phase="PREGAME",
        transport="unit_test_fixture",
        source_payload_sha256=hashlib.sha256(f"{provider}-{gamepk}".encode()).hexdigest(),
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
        "source": OFFICIAL_SCHEDULE_SOURCE,
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


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step12b_live_runtime_assembly_v1"
    assert SCHEMA_VERSION == 1
    assert STEP12B_BASE_MAIN_SHA == BASE_SHA
    assert ASSEMBLY_STATUS == "STEP12B_LIVE_RUNTIME_ASSEMBLY_READY"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP12B_LIVE_RUNTIME_ASSEMBLY_GREEN"
    assert OFFICIAL_SCHEDULE_SOURCE == "MLB Stats API"
    assert MAX_OFFICIAL_GAMES == 50


def test_manifest_pins_step12a_exactly():
    manifest = live_runtime_assembly_manifest()
    assert manifest["step12b_base_main_sha"] == BASE_SHA
    assert manifest["step12a_runtime_status_required"] == STEP12A_STATUS
    assert manifest["step12a_runtime_mode_required"] == STEP12A_MODE
    assert manifest["step12a_final_certification_marker_required"] == STEP12A_MARKER
    assert manifest["official_schedule_source_required"] == OFFICIAL_SCHEDULE_SOURCE


@pytest.mark.parametrize(
    "key",
    [
        "official_schedule_supplied_by_caller",
        "provider_snapshots_supplied_by_caller",
        "exact_official_game_id_join_required",
        "every_provider_game_id_must_exist_in_official_schedule",
        "duplicate_official_game_ids_forbidden",
        "step12a_shadow_runtime_executed_after_identity_gate",
        "step12a_shadow_runtime_revalidated",
        "freshness_gate_preserved",
        "source_complete_gate_preserved",
        "same_line_gate_preserved",
        "deterministic_assembly",
        "future_controlled_runtime_activation_required",
    ],
)
def test_manifest_required_guards_are_true(key):
    assert live_runtime_assembly_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "network_io_added_by_step12b",
        "live_secondary_provider_network_calls_enabled",
        "production_api_wiring_added_by_step12b",
        "production_runtime_wiring_added_by_step12b",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step12b",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "team_name_join_allowed",
        "player_name_join_allowed",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "shadow_output_as_model_input_allowed",
        "shadow_output_as_sportsbook_input_allowed",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ],
)
def test_manifest_forbidden_behavior_stays_false(key):
    assert live_runtime_assembly_manifest()[key] is False


def test_manifest_preserves_all_protected_invariants():
    manifest = live_runtime_assembly_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_manifest_isolation():
    first = live_runtime_assembly_manifest()
    first["official_schedule_source_required"] = "mutated"
    assert live_runtime_assembly_manifest()["official_schedule_source_required"] == OFFICIAL_SCHEDULE_SOURCE


def test_happy_two_provider_live_assembly():
    assembly = _assembly()
    assert assembly["runtime_mode"] == "SHADOW_ONLY"
    assert assembly["official_schedule_game_count"] == 2
    assert assembly["official_game_ids"] == [GAME1, GAME2]
    assert assembly["provider_snapshot_count"] == 2
    assert assembly["provider_game_ids"] == [GAME1]
    assert assembly["matched_official_game_count"] == 1
    assert assembly["unmatched_official_game_ids"] == [GAME2]
    assert assembly["exact_official_game_id_join_verified"] is True
    assert assembly["consensus_ready_market_count"] == 3
    assert assembly["shadow_cycle_validated"] is True


def test_happy_assembly_validates_exactly():
    assembly = _assembly()
    assert validate_live_runtime_assembly(assembly) == {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "assembly_valid": True,
        "failures": [],
    }


def test_assembly_is_deterministic():
    assert _assembly() == _assembly()


def test_schedule_input_order_does_not_change_assembly():
    first = _schedule(_game(GAME1), _game(GAME2))
    second = _schedule(_game(GAME2), _game(GAME1))
    assert _assembly(schedule=first) == _assembly(schedule=second)


def test_provider_input_order_does_not_change_assembly():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    assert _assembly([fd, dk]) == _assembly([dk, fd])


def test_assembly_does_not_mutate_inputs_or_manifest():
    schedule = _schedule()
    snapshots = [_snapshot("fanduel"), _snapshot("draftkings")]
    manifest = shadow_runtime_manifest()
    before_schedule = deepcopy(schedule)
    before_snapshots = deepcopy(snapshots)
    before_manifest = deepcopy(manifest)
    assemble_live_runtime_shadow(
        schedule,
        snapshots,
        assembled_at_utc=ASSEMBLED,
        evaluated_at_utc=EVALUATED,
        step12a_manifest=manifest,
    )
    assert schedule == before_schedule
    assert snapshots == before_snapshots
    assert manifest == before_manifest


def test_unmatched_official_games_are_allowed_but_never_synthesized():
    assembly = _assembly([_snapshot("fanduel")])
    assert assembly["provider_game_ids"] == [GAME1]
    assert assembly["unmatched_official_game_ids"] == [GAME2]
    assert assembly["synthetic_game_id_used"] is False


def test_multi_game_provider_snapshots_bind_by_exact_gamepk():
    snapshots = [
        _snapshot("fanduel", gamepk=GAME1),
        _snapshot("fanduel", gamepk=GAME2),
    ]
    assembly = _assembly(snapshots)
    assert assembly["provider_game_ids"] == [GAME1, GAME2]
    assert assembly["matched_official_game_count"] == 2
    assert assembly["unmatched_official_game_count"] == 0
    assert assembly["unmatched_official_game_ids"] == []


def test_team_names_are_metadata_not_identity():
    schedule = _schedule(_game(GAME1, away="Totally Different Away", home="Totally Different Home"))
    assembly = _assembly([_snapshot("fanduel")], schedule=schedule)
    assert assembly["provider_game_ids"] == [GAME1]
    assert assembly["team_name_join_used"] is False


def test_unicode_schedule_metadata_roundtrips():
    game = _game(GAME1, away="Montréal Étoiles", home="東京クラブ")
    game["venue"] = "Parc Montréal – 東京"
    assembly = _assembly([_snapshot("fanduel")], schedule=_schedule(game))
    assert assembly["official_schedule"]["games"][0]["away_team"] == "Montréal Étoiles"
    assert validate_live_runtime_assembly(assembly)["assembly_valid"] is True


def test_assembly_hash_is_lowercase_sha256():
    value = _assembly()["assembly_sha256"]
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def test_stale_primary_shadow_failover_behavior_is_preserved():
    fd = _snapshot("fanduel", observed="2026-09-01T18:10:00Z")
    dk = _snapshot("draftkings", observed=ASSEMBLED)
    assembly = _assembly([fd, dk], max_age_seconds=60)
    assert assembly["stale_provider_slot_count"] == 1
    assert assembly["shadow_failover_candidate_count"] == 3
    assert assembly["production_provider_failover_used"] is False


def test_source_complete_gate_is_preserved():
    fd = _snapshot("fanduel", source_complete=False)
    dk = _snapshot("draftkings", source_complete=True)
    assembly = _assembly([fd, dk])
    assert assembly["consensus_ready_market_count"] == 0
    assert assembly["shadow_failover_candidate_count"] == 3


def test_same_line_gate_is_preserved():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings", total_line=9.0, away_rl=2.5)
    assembly = _assembly([fd, dk])
    assert assembly["consensus_ready_market_count"] == 1


def test_single_provider_is_valid_shadow_assembly_without_consensus():
    assembly = _assembly([_snapshot("fanduel")])
    assert assembly["consensus_ready_market_count"] == 0
    assert assembly["shadow_failover_candidate_count"] == 0


def test_schedule_must_be_mapping():
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="official_schedule must be a mapping"):
        _assembly(schedule="bad")


def test_schedule_rejects_unknown_top_level_key():
    schedule = _schedule()
    schedule["extra"] = True
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="unsupported keys"):
        _assembly(schedule=schedule)


@pytest.mark.parametrize("source", [None, "MLB", "mlb stats api", 1, True])
def test_schedule_source_must_match_exactly(source):
    schedule = _schedule()
    schedule["source"] = source
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="source must equal"):
        _assembly(schedule=schedule)


@pytest.mark.parametrize("value", [None, "2026-9-1", "09-01-2026", "2026-09-01 ", 20260901])
def test_schedule_date_is_strict_canonical_yyyy_mm_dd(value):
    schedule = _schedule()
    schedule["date"] = value
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError):
        _assembly(schedule=schedule)


@pytest.mark.parametrize("value", [True, False, -1, 2.0, "2", None])
def test_schedule_game_count_is_strict_nonnegative_integer(value):
    schedule = _schedule()
    schedule["game_count"] = value
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError):
        _assembly(schedule=schedule)


def test_schedule_game_count_must_equal_games_length():
    schedule = _schedule()
    schedule["game_count"] = 1
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="exactly equal"):
        _assembly(schedule=schedule)


@pytest.mark.parametrize("value", [None, "bad", b"bad", {}, 42])
def test_schedule_games_must_be_sequence(value):
    schedule = _schedule()
    schedule["games"] = value
    schedule["game_count"] = 0
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="must be a sequence"):
        _assembly(schedule=schedule)


def test_schedule_games_must_not_be_empty():
    schedule = _schedule()
    schedule["games"] = []
    schedule["game_count"] = 0
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="must not be empty"):
        _assembly(schedule=schedule)


def test_schedule_games_have_hard_maximum():
    rows = [_game(900000 + i) for i in range(MAX_OFFICIAL_GAMES + 1)]
    schedule = _schedule(*rows)
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="exceeds maximum"):
        _assembly([_snapshot("fanduel")], schedule=schedule)


def test_every_schedule_game_must_be_mapping():
    schedule = _schedule()
    schedule["games"][1] = "bad"
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="must be a mapping"):
        _assembly(schedule=schedule)


def test_schedule_game_rejects_unknown_key():
    schedule = _schedule()
    schedule["games"][0]["game_id"] = GAME1
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="unsupported keys"):
        _assembly(schedule=schedule)


@pytest.mark.parametrize("value", [0, -1, True, False, "777001", 777001.0, None])
def test_schedule_gamepk_must_be_strict_positive_integer(value):
    schedule = _schedule()
    schedule["games"][0]["game_pk"] = value
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="positive integer"):
        _assembly(schedule=schedule)


def test_duplicate_official_gamepk_is_forbidden_even_for_identical_rows():
    schedule = _schedule(_game(GAME1), _game(GAME1))
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="duplicate official gamePk"):
        _assembly(schedule=schedule)


@pytest.mark.parametrize(
    "value",
    ["2026-09-01T23:10:00+00:00", "badZ", "2026-09-01 23:10:00Z", 123, True],
)
def test_schedule_game_date_utc_is_strict(value):
    schedule = _schedule()
    schedule["games"][0]["game_date_utc"] = value
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError):
        _assembly(schedule=schedule)


def test_schedule_game_date_utc_may_be_none():
    schedule = _schedule(_game(GAME1))
    schedule["games"][0]["game_date_utc"] = None
    assert _assembly([_snapshot("fanduel")], schedule=schedule)["official_game_ids"] == [GAME1]


@pytest.mark.parametrize("field", ["status", "venue", "away_team", "home_team", "away_probable_pitcher", "home_probable_pitcher"])
def test_schedule_optional_text_rejects_non_string(field):
    schedule = _schedule()
    schedule["games"][0][field] = 123
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError):
        _assembly(schedule=schedule)


def test_schedule_optional_text_rejects_blank_string():
    schedule = _schedule()
    schedule["games"][0]["venue"] = "   "
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="must not be blank"):
        _assembly(schedule=schedule)


def test_provider_snapshots_must_be_sequence():
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="provider_snapshots must be a sequence"):
        assemble_live_runtime_shadow(
            _schedule(),
            None,
            assembled_at_utc=ASSEMBLED,
            evaluated_at_utc=EVALUATED,
            step12a_manifest=shadow_runtime_manifest(),
        )


def test_provider_snapshots_must_not_be_empty():
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="must not be empty"):
        _assembly([])


def test_every_provider_snapshot_must_be_mapping():
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="must be a mapping"):
        _assembly([_snapshot("fanduel"), "bad"])


@pytest.mark.parametrize("value", [0, -1, True, False, "777001", 777001.0, None])
def test_provider_snapshot_gamepk_must_be_strict_positive_integer(value):
    row = _snapshot("fanduel")
    row["official_game_id"] = value
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="positive integer"):
        _assembly([row])


def test_provider_snapshot_gamepk_absent_from_official_schedule_fails_closed():
    schedule = _schedule(_game(GAME1))
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="absent from official schedule"):
        _assembly([_snapshot("fanduel", gamepk=GAME2)], schedule=schedule)


def test_step12a_manifest_must_be_mapping():
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="step12a_manifest must be a mapping"):
        _assembly(step12a_manifest=None)


def test_step12a_manifest_must_match_exactly():
    manifest = shadow_runtime_manifest()
    manifest["production_runtime_wiring_added_by_step12a"] = True
    with pytest.raises(MLBStep12BLiveRuntimeAssemblyError, match="manifest mismatch"):
        _assembly(step12a_manifest=manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("assembled_at_utc", "2026-09-01T18:20:00+00:00"),
        ("assembled_at_utc", "badZ"),
        ("evaluated_at_utc", "2026-09-01T18:20:30+00:00"),
        ("evaluated_at_utc", None),
    ],
)
def test_step12a_timestamp_guards_are_preserved(field, value):
    with pytest.raises(Exception):
        _assembly(**{field: value})


def test_evaluation_cannot_precede_assembly():
    with pytest.raises(Exception, match="cannot be before"):
        _assembly(evaluated_at_utc="2026-09-01T18:19:59Z")


@pytest.mark.parametrize("max_age", [True, False, 0, -1, 3601, 1.5, "180"])
def test_step12a_max_age_guard_is_preserved(max_age):
    with pytest.raises(Exception):
        _assembly(max_age_seconds=max_age)


def test_assembly_records_zero_production_side_effects():
    assembly = _assembly()
    assert assembly["network_io_performed"] is False
    assert assembly["live_secondary_provider_network_calls"] == 0
    assert assembly["production_api_wiring"] is False
    assert assembly["production_runtime_wiring"] is False
    assert assembly["production_provider_consensus_used"] is False
    assert assembly["production_provider_failover_used"] is False
    assert assembly["best_price_selection_used"] is False
    assert assembly["provider_weighting_used"] is False
    assert assembly["production_database_writes"] == 0
    assert assembly["persistence_schema_changed"] is False
    assert assembly["price_fabrication_used"] is False
    assert assembly["fallback_price_fabrication_used"] is False
    assert assembly["team_name_join_used"] is False
    assert assembly["player_name_join_used"] is False
    assert assembly["fuzzy_matching_used"] is False
    assert assembly["synthetic_game_id_used"] is False
    assert assembly["shadow_output_as_model_input"] is False
    assert assembly["shadow_output_as_sportsbook_input"] is False
    assert assembly["persisted_snapshot_as_model_input"] is False
    assert assembly["persisted_snapshot_as_sportsbook_input"] is False


def test_validator_rejects_non_mapping():
    result = validate_live_runtime_assembly(None)
    assert result["assembly_valid"] is False
    assert result["failures"] == ["STEP12B_ASSEMBLY_NOT_MAPPING"]


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("runtime_mode", "LIVE"),
        ("exact_official_game_id_join_verified", False),
        ("production_runtime_wiring", True),
        ("production_provider_failover_used", True),
        ("production_database_writes", 1),
        ("price_fabrication_used", True),
        ("team_name_join_used", True),
        ("fuzzy_matching_used", True),
        ("synthetic_game_id_used", True),
        ("assembly_sha256", "0" * 64),
    ],
)
def test_validator_rejects_top_level_tampering(field, bad_value):
    assembly = _assembly()
    assembly[field] = bad_value
    result = validate_live_runtime_assembly(assembly)
    assert result["assembly_valid"] is False


def test_validator_rejects_schedule_tampering():
    assembly = _assembly()
    assembly["official_schedule"]["games"][0]["home_team"] = "tampered"
    assert validate_live_runtime_assembly(assembly)["assembly_valid"] is False


def test_validator_rejects_nested_shadow_cycle_tampering():
    assembly = _assembly()
    assembly["shadow_cycle"]["production_runtime_wiring"] = True
    assert validate_live_runtime_assembly(assembly)["assembly_valid"] is False


def test_validator_rejects_missing_shadow_cycle():
    assembly = _assembly()
    assembly.pop("shadow_cycle")
    result = validate_live_runtime_assembly(assembly)
    assert result["assembly_valid"] is False
    assert any("shadow_cycle must be a mapping" in item for item in result["failures"])
