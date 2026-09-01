from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11_final_provider_expansion_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP11_MARKER,
    FINAL_FREEZE_STATUS as STEP11_STATUS,
    final_provider_expansion_freeze_manifest,
)
from sports_api.mlb_step11a_provider_contract_v1 import build_market_provider_game_snapshot
from sports_api.mlb_step12a_shadow_runtime_runner_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MLBStep12AShadowRuntimeError,
    RUNTIME_MODE,
    RUNTIME_STATUS,
    SCHEMA_VERSION,
    STEP12A_BASE_MAIN_SHA,
    run_shadow_runtime_cycle,
    shadow_runtime_manifest,
    validate_shadow_runtime_cycle,
)

BASE_SHA = "388c79480e916f7d9123b4f6deef6b6938ac8d2b"
ASSEMBLED = "2026-09-01T18:20:00Z"
EVALUATED = "2026-09-01T18:20:30Z"
GAMEPK = 777001
_DEFAULT = object()


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
    observed: str = ASSEMBLED,
    collected: str | None = None,
    source_complete: bool = True,
    total_line: float = 8.5,
    away_rl: float = 1.5,
):
    name = {"fanduel": "FanDuel", "draftkings": "DraftKings"}[provider]
    prefix = "fd" if provider == "fanduel" else "dk"
    return build_market_provider_game_snapshot(
        provider_key=provider,
        provider_name=name,
        provider_event_id=f"{prefix}-event-{GAMEPK}",
        official_game_id=GAMEPK,
        observed_at_utc=observed,
        source_collected_at_utc=collected or observed,
        market_phase="PREGAME",
        transport="unit_test_fixture",
        source_payload_sha256=hashlib.sha256(f"{provider}-payload".encode()).hexdigest(),
        markets=_markets(prefix, total_line=total_line, away_rl=away_rl),
        source_complete=source_complete,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )


def _cycle(snapshots=_DEFAULT, **kwargs):
    if snapshots is _DEFAULT:
        snapshots = [_snapshot("fanduel"), _snapshot("draftkings")]
    args = {
        "assembled_at_utc": ASSEMBLED,
        "evaluated_at_utc": EVALUATED,
        "step11_final_manifest": final_provider_expansion_freeze_manifest(),
    }
    args.update(kwargs)
    return run_shadow_runtime_cycle(snapshots, **args)


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step12a_shadow_runtime_cycle_v1"
    assert SCHEMA_VERSION == 1
    assert STEP12A_BASE_MAIN_SHA == BASE_SHA
    assert RUNTIME_STATUS == "STEP12A_SHADOW_RUNTIME_RUNNER_READY"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP12A_SHADOW_RUNTIME_RUNNER_GREEN"


def test_manifest_pins_step11_final_freeze():
    manifest = shadow_runtime_manifest()
    assert manifest["step11_final_freeze_status_required"] == STEP11_STATUS
    assert manifest["step11_final_certification_marker_required"] == STEP11_MARKER
    assert manifest["step12a_base_main_sha"] == BASE_SHA


def test_manifest_runtime_boundary_is_shadow_only():
    manifest = shadow_runtime_manifest()
    for key in (
        "provider_snapshots_supplied_by_caller",
        "step11c_shadow_board_executed",
        "step11d_shadow_policy_executed",
        "deterministic_runtime_cycle",
        "exact_official_game_id_required",
        "freshness_gate_required",
        "source_complete_gate_required",
        "same_line_required_for_run_line_total_consensus",
        "future_live_runtime_activation_required",
    ):
        assert manifest[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "network_io_added_by_step12a",
        "live_secondary_provider_network_calls_enabled",
        "production_api_wiring_added_by_step12a",
        "production_runtime_wiring_added_by_step12a",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step12a",
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
    assert shadow_runtime_manifest()[key] is False


def test_manifest_preserves_all_protected_invariants():
    manifest = shadow_runtime_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_manifest_isolation():
    first = shadow_runtime_manifest()
    first["primary_provider"] = "mutated"
    assert shadow_runtime_manifest()["primary_provider"] == "fanduel"


def test_happy_two_provider_cycle():
    cycle = _cycle()
    assert cycle["runtime_mode"] == "SHADOW_ONLY"
    assert cycle["source_snapshot_count"] == 2
    assert cycle["unique_game_count"] == 1
    assert cycle["game_phase_group_count"] == 1
    assert cycle["dual_provider_game_phase_group_count"] == 1
    assert cycle["consensus_ready_market_count"] == 3
    assert cycle["shadow_failover_candidate_count"] == 0
    assert cycle["stale_provider_slot_count"] == 0
    assert cycle["shadow_cycle_completed"] is True


def test_happy_cycle_validates_exactly():
    cycle = _cycle()
    assert validate_shadow_runtime_cycle(cycle) == {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "cycle_valid": True,
        "failures": [],
    }


def test_runtime_cycle_is_deterministic():
    assert _cycle() == _cycle()


def test_input_order_does_not_change_cycle():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    assert _cycle([fd, dk]) == _cycle([dk, fd])


def test_runtime_does_not_mutate_inputs_or_manifest():
    snapshots = [_snapshot("fanduel"), _snapshot("draftkings")]
    manifest = final_provider_expansion_freeze_manifest()
    snapshots_before = deepcopy(snapshots)
    manifest_before = deepcopy(manifest)
    _cycle(snapshots, step11_final_manifest=manifest)
    assert snapshots == snapshots_before
    assert manifest == manifest_before


def test_cycle_hash_is_lowercase_sha256():
    value = _cycle()["cycle_sha256"]
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def test_duplicate_identical_snapshot_is_deduplicated_by_step11c():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    cycle = _cycle([fd, deepcopy(fd), dk])
    assert cycle["source_snapshot_count"] == 3
    assert cycle["shadow_board"]["exact_duplicate_count"] == 1
    assert cycle["dual_provider_game_phase_group_count"] == 1


def test_single_fanduel_is_allowed_but_has_no_consensus():
    cycle = _cycle([_snapshot("fanduel")])
    assert cycle["consensus_ready_market_count"] == 0
    assert cycle["shadow_failover_candidate_count"] == 0


def test_single_draftkings_becomes_shadow_failover_candidate_only():
    cycle = _cycle([_snapshot("draftkings")])
    assert cycle["consensus_ready_market_count"] == 0
    assert cycle["shadow_failover_candidate_count"] == 3
    assert cycle["production_provider_failover_used"] is False


def test_stale_primary_with_fresh_fallback_marks_three_shadow_failovers():
    fd = _snapshot("fanduel", observed="2026-09-01T18:10:00Z")
    dk = _snapshot("draftkings", observed="2026-09-01T18:20:00Z")
    cycle = _cycle([fd, dk], max_age_seconds=60)
    assert cycle["stale_provider_slot_count"] == 1
    assert cycle["shadow_failover_candidate_count"] == 3
    assert cycle["consensus_ready_market_count"] == 0


def test_both_stale_produces_no_route_and_no_consensus():
    fd = _snapshot("fanduel", observed="2026-09-01T18:00:00Z")
    dk = _snapshot("draftkings", observed="2026-09-01T18:00:00Z")
    cycle = _cycle([fd, dk], max_age_seconds=60)
    assert cycle["stale_provider_slot_count"] == 2
    assert cycle["shadow_failover_candidate_count"] == 0
    assert cycle["consensus_ready_market_count"] == 0


def test_line_mismatch_keeps_moneyline_consensus_only():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings", total_line=9.0, away_rl=2.5)
    cycle = _cycle([fd, dk])
    assert cycle["consensus_ready_market_count"] == 1


def test_source_complete_gate_excludes_incomplete_primary():
    fd = _snapshot("fanduel", source_complete=False)
    dk = _snapshot("draftkings", source_complete=True)
    cycle = _cycle([fd, dk])
    assert cycle["shadow_failover_candidate_count"] == 3
    assert cycle["consensus_ready_market_count"] == 0


@pytest.mark.parametrize("value", [None, "bad", b"bad", 42, {}])
def test_source_snapshots_must_be_sequence(value):
    with pytest.raises(MLBStep12AShadowRuntimeError):
        _cycle(value)


def test_source_snapshots_must_not_be_empty():
    with pytest.raises(MLBStep12AShadowRuntimeError):
        _cycle([])


def test_source_snapshots_have_hard_maximum():
    row = _snapshot("fanduel")
    with pytest.raises(MLBStep12AShadowRuntimeError):
        _cycle([row] * 501)


def test_every_snapshot_must_be_mapping():
    with pytest.raises(MLBStep12AShadowRuntimeError):
        _cycle([_snapshot("fanduel"), "bad"])


def test_step11_manifest_must_be_mapping():
    with pytest.raises(MLBStep12AShadowRuntimeError):
        _cycle(step11_final_manifest=None)


def test_step11_manifest_must_match_exactly():
    manifest = final_provider_expansion_freeze_manifest()
    manifest["production_provider_failover_enabled"] = True
    with pytest.raises(MLBStep12AShadowRuntimeError, match="manifest mismatch"):
        _cycle(step11_final_manifest=manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("assembled_at_utc", "2026-09-01T18:20:00+00:00"),
        ("assembled_at_utc", "badZ"),
        ("evaluated_at_utc", "2026-09-01T18:20:30+00:00"),
        ("evaluated_at_utc", None),
    ],
)
def test_cycle_timestamps_are_strict_utc_z(field, value):
    with pytest.raises(MLBStep12AShadowRuntimeError):
        _cycle(**{field: value})


def test_evaluation_cannot_precede_assembly():
    with pytest.raises(MLBStep12AShadowRuntimeError, match="cannot be before"):
        _cycle(evaluated_at_utc="2026-09-01T18:19:59Z")


def test_source_snapshot_cannot_be_from_future_of_assembly():
    row = _snapshot("fanduel", observed="2026-09-01T18:21:00Z")
    with pytest.raises(Exception):
        _cycle([row])


@pytest.mark.parametrize("max_age", [True, False, 0, -1, 3601, 1.5, "180"])
def test_max_age_fail_closed(max_age):
    with pytest.raises(Exception):
        _cycle(max_age_seconds=max_age)


@pytest.mark.parametrize(
    "primary,fallback",
    [
        ("badbook", "draftkings"),
        ("fanduel", "badbook"),
        ("fanduel", "fanduel"),
        ("draftkings", "draftkings"),
    ],
)
def test_provider_route_fail_closed(primary, fallback):
    with pytest.raises(Exception):
        _cycle(primary_provider=primary, fallback_provider=fallback)


def test_invalid_official_game_id_in_source_fails_closed():
    row = _snapshot("fanduel")
    row["official_game_id"] = str(GAMEPK)
    with pytest.raises(Exception):
        _cycle([row])


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("fuzzy_matching_used", True),
        ("synthetic_game_id_used", True),
        ("price_fabrication_used", True),
        ("exact_official_game_id_verified", False),
    ],
)
def test_source_identity_and_fabrication_guards_fail_closed(field, bad_value):
    row = _snapshot("fanduel")
    row[field] = bad_value
    with pytest.raises(Exception):
        _cycle([row])


def test_cycle_records_zero_production_side_effects():
    cycle = _cycle()
    assert cycle["network_io_performed"] is False
    assert cycle["live_secondary_provider_network_calls"] == 0
    assert cycle["production_api_wiring"] is False
    assert cycle["production_runtime_wiring"] is False
    assert cycle["production_provider_consensus_used"] is False
    assert cycle["production_provider_failover_used"] is False
    assert cycle["best_price_selection_used"] is False
    assert cycle["provider_weighting_used"] is False
    assert cycle["production_database_writes"] == 0
    assert cycle["price_fabrication_used"] is False
    assert cycle["fallback_price_fabrication_used"] is False
    assert cycle["shadow_output_as_model_input"] is False
    assert cycle["shadow_output_as_sportsbook_input"] is False


def test_validate_rejects_non_mapping():
    result = validate_shadow_runtime_cycle(None)
    assert result["cycle_valid"] is False
    assert result["failures"] == ["STEP12A_CYCLE_NOT_MAPPING"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c.__setitem__("source_snapshot_count", 999),
        lambda c: c.__setitem__("production_runtime_wiring", True),
        lambda c: c.__setitem__("cycle_sha256", "0" * 64),
        lambda c: c["shadow_board"].__setitem__("unique_game_count", 99),
        lambda c: c["shadow_policy"].__setitem__("consensus_ready_market_count", 99),
    ],
)
def test_validate_detects_tampering(mutation):
    cycle = _cycle()
    mutation(cycle)
    result = validate_shadow_runtime_cycle(cycle)
    assert result["cycle_valid"] is False
    assert result["failures"]


def test_validator_does_not_mutate_cycle():
    cycle = _cycle()
    before = deepcopy(cycle)
    validate_shadow_runtime_cycle(cycle)
    assert cycle == before
