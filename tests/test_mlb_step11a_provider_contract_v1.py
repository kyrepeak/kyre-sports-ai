from __future__ import annotations

from copy import deepcopy
import math

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    CONTRACT_STATUS,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MLBProviderContractError,
    SCHEMA_VERSION,
    STEP11A_BASE_MAIN_SHA,
    SUPPORTED_CORE_MARKETS,
    SUPPORTED_MARKET_PHASES,
    build_market_provider_game_snapshot,
    provider_contract_manifest,
    validate_market_provider_game_snapshot,
)


def _full_markets() -> dict:
    return {
        "moneyline": {
            "market_id": "ml-1",
            "market_time_utc": "2026-09-01T17:20:00Z",
            "away_odds": 120,
            "home_odds": -135,
            "away_selection_id": 101,
            "home_selection_id": "102",
        },
        "run_line": {
            "market_id": "rl-1",
            "away_line": 1.5,
            "away_odds": -105,
            "home_line": -1.5,
            "home_odds": -115,
            "away_selection_id": "201",
            "home_selection_id": 202,
        },
        "total": {
            "market_id": "tot-1",
            "line": 8.5,
            "over_odds": -110,
            "under_odds": -110,
            "over_selection_id": "301",
            "under_selection_id": 302,
        },
    }


def _args(**overrides):
    args = {
        "provider_key": "fanduel",
        "provider_name": "FanDuel",
        "provider_event_id": "fd-event-123",
        "official_game_id": 777001,
        "observed_at_utc": "2026-09-01T17:20:01Z",
        "source_collected_at_utc": "2026-09-01T17:20:00Z",
        "market_phase": "IN_PLAY",
        "transport": "anonymous_public_get_only",
        "source_payload_sha256": "a" * 64,
        "markets": _full_markets(),
        "source_complete": True,
        "exact_official_game_id_verified": True,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "price_fabrication_used": False,
        "step10_final_freeze_status": STEP10_STATUS,
        "step10_final_certification_marker": STEP10_MARKER,
    }
    args.update(overrides)
    return args


def test_manifest_freezes_provider_contract_without_activation():
    manifest = provider_contract_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == SCHEMA_VERSION == 1
    assert manifest["step11a_base_main_sha"] == STEP11A_BASE_MAIN_SHA
    assert STEP11A_BASE_MAIN_SHA == "6de8d3b466f661477a1e676fb397e6b9bbdb977a"
    assert manifest["contract_status"] == CONTRACT_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["step10_final_freeze_status_required"] == STEP10_STATUS
    assert manifest["step10_final_certification_marker_required"] == STEP10_MARKER
    assert tuple(manifest["supported_market_phases"]) == SUPPORTED_MARKET_PHASES
    assert tuple(manifest["supported_core_markets"]) == SUPPORTED_CORE_MARKETS
    assert manifest["network_io_added_by_step11a"] is False
    assert manifest["second_provider_activated_by_step11a"] is False
    assert manifest["production_runtime_wiring_added_by_step11a"] is False
    assert manifest["persistence_schema_changed_by_step11a"] is False
    assert manifest["automatic_production_writes_enabled"] is False


def test_manifest_preserves_no_fabrication_and_exact_identity():
    manifest = provider_contract_manifest()
    assert manifest["exact_official_game_id_required"] is True
    assert manifest["missing_markets_must_be_omitted"] is True
    assert manifest["partial_market_objects_allowed"] is False
    assert manifest["price_fabrication_allowed"] is False
    assert manifest["fallback_price_fabrication_allowed"] is False
    assert manifest["fuzzy_matching_allowed"] is False
    assert manifest["synthetic_game_id_allowed"] is False
    assert manifest["team_name_join_allowed_downstream"] is False


def test_manifest_preserves_all_step9_protected_invariants():
    manifest = provider_contract_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_manifest_isolation():
    first = provider_contract_manifest()
    first["supported_core_markets"].append("invented")
    first["supported_market_phases"].append("FAKE")
    second = provider_contract_manifest()
    assert tuple(second["supported_core_markets"]) == SUPPORTED_CORE_MARKETS
    assert tuple(second["supported_market_phases"]) == SUPPORTED_MARKET_PHASES


def test_build_full_inplay_snapshot():
    snapshot = build_market_provider_game_snapshot(**_args())
    assert snapshot["data_type"] == DATA_TYPE
    assert snapshot["schema_version"] == 1
    assert snapshot["provider_key"] == "fanduel"
    assert snapshot["provider_name"] == "FanDuel"
    assert snapshot["official_game_id"] == 777001
    assert snapshot["market_phase"] == "IN_PLAY"
    assert snapshot["market_count"] == 3
    assert snapshot["fully_priced"] is True
    assert snapshot["market_availability"] == {
        "moneyline": True,
        "run_line": True,
        "total": True,
    }
    assert snapshot["exact_official_game_id_verified"] is True
    assert snapshot["fuzzy_matching_used"] is False
    assert snapshot["synthetic_game_id_used"] is False
    assert snapshot["price_fabrication_used"] is False
    assert len(snapshot["snapshot_sha256"]) == 64


def test_build_partial_snapshot_omits_missing_markets_without_placeholders():
    markets = {"moneyline": _full_markets()["moneyline"]}
    snapshot = build_market_provider_game_snapshot(**_args(markets=markets))
    assert list(snapshot["markets"]) == ["moneyline"]
    assert snapshot["market_count"] == 1
    assert snapshot["fully_priced"] is False
    assert snapshot["market_availability"] == {
        "moneyline": True,
        "run_line": False,
        "total": False,
    }


def test_pregame_phase_is_supported():
    snapshot = build_market_provider_game_snapshot(**_args(market_phase="PREGAME"))
    assert snapshot["market_phase"] == "PREGAME"


def test_builder_is_deterministic():
    first = build_market_provider_game_snapshot(**_args())
    second = build_market_provider_game_snapshot(**_args())
    assert first == second


def test_record_key_contains_exact_provider_game_phase_observation_and_hash():
    snapshot = build_market_provider_game_snapshot(**_args())
    assert snapshot["record_key"] == (
        "mlb:777001:provider:fanduel:IN_PLAY:2026-09-01T17:20:01Z:" + "a" * 64
    )


def test_selection_ids_are_canonical_strings_or_none():
    snapshot = build_market_provider_game_snapshot(**_args())
    assert snapshot["markets"]["moneyline"]["away_selection_id"] == "101"
    assert snapshot["markets"]["run_line"]["home_selection_id"] == "202"
    assert snapshot["markets"]["total"]["under_selection_id"] == "302"


def test_absent_selection_ids_are_none():
    markets = _full_markets()
    del markets["moneyline"]["away_selection_id"]
    del markets["moneyline"]["home_selection_id"]
    snapshot = build_market_provider_game_snapshot(**_args(markets=markets))
    assert snapshot["markets"]["moneyline"]["away_selection_id"] is None
    assert snapshot["markets"]["moneyline"]["home_selection_id"] is None


def test_market_time_may_be_absent():
    markets = _full_markets()
    markets["moneyline"].pop("market_time_utc")
    snapshot = build_market_provider_game_snapshot(**_args(markets=markets))
    assert snapshot["markets"]["moneyline"]["market_time_utc"] is None


def test_validator_accepts_exact_snapshot():
    snapshot = build_market_provider_game_snapshot(**_args())
    result = validate_market_provider_game_snapshot(snapshot)
    assert result["snapshot_valid"] is True
    assert result["failures"] == []


def test_validator_is_non_mutating():
    snapshot = build_market_provider_game_snapshot(**_args())
    before = deepcopy(snapshot)
    validate_market_provider_game_snapshot(snapshot)
    assert snapshot == before


def test_validator_rejects_non_mapping():
    result = validate_market_provider_game_snapshot(None)
    assert result["snapshot_valid"] is False
    assert result["failures"] == ["STEP11A_SNAPSHOT_NOT_MAPPING"]


@pytest.mark.parametrize(
    "provider_key",
    ["", "FanDuel", "fan duel", "-fanduel", "_fanduel", "fd!", "a" * 33, 123],
)
def test_invalid_provider_keys_fail_closed(provider_key):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(provider_key=provider_key))


@pytest.mark.parametrize("official_game_id", [True, False, 0, -1, 7.0, "777001", None])
def test_official_game_id_must_be_exact_positive_integer(official_game_id):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(official_game_id=official_game_id))


@pytest.mark.parametrize("market_phase", ["", "LIVE", "in_play", "INPLAY", None, 1])
def test_market_phase_is_exact_enum(market_phase):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(market_phase=market_phase))


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_at_utc", "2026-09-01T17:20:01+00:00"),
        ("observed_at_utc", "2026-09-01T10:20:01-07:00"),
        ("observed_at_utc", "bad"),
        ("source_collected_at_utc", "2026-09-01T17:20:00+00:00"),
        ("source_collected_at_utc", "bad"),
    ],
)
def test_timestamps_must_be_utc_rfc3339_z(field, value):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(**{field: value}))


def test_source_collection_time_cannot_be_after_observation():
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(
            **_args(source_collected_at_utc="2026-09-01T17:20:02Z")
        )


@pytest.mark.parametrize("payload_hash", ["", "A" * 64, "g" * 64, "a" * 63, "a" * 65, None])
def test_source_payload_hash_must_be_lowercase_sha256(payload_hash):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(source_payload_sha256=payload_hash))


@pytest.mark.parametrize("markets", [{}, None, [], {"spread": {"market_id": "x"}}])
def test_markets_must_contain_only_real_supported_core_markets(markets):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


def test_empty_or_partial_market_object_is_rejected_not_fabricated():
    for market in (
        {"moneyline": {}},
        {"moneyline": {"market_id": "ml", "away_odds": 110}},
        {"total": {"market_id": "t", "line": 8.5, "over_odds": -110}},
    ):
        with pytest.raises(MLBProviderContractError):
            build_market_provider_game_snapshot(**_args(markets=market))


def test_unknown_fields_inside_market_are_rejected():
    markets = _full_markets()
    markets["moneyline"]["consensus_price"] = -110
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


@pytest.mark.parametrize("odds", [True, False, 0, 99, -99, 100001, -100001, 110.0, "-110", None])
def test_american_prices_are_strict_and_never_coerced(odds):
    markets = _full_markets()
    markets["moneyline"]["away_odds"] = odds
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


def test_run_line_sides_must_be_exact_opposites():
    markets = _full_markets()
    markets["run_line"]["home_line"] = -2.5
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


@pytest.mark.parametrize("line", [True, "1.5", float("nan"), float("inf"), 101, -101])
def test_run_line_requires_bounded_finite_numeric_line(line):
    markets = _full_markets()
    markets["run_line"]["away_line"] = line
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


@pytest.mark.parametrize("line", [True, "8.5", float("nan"), float("inf"), -0.5, 101])
def test_total_requires_nonnegative_bounded_finite_line(line):
    markets = _full_markets()
    markets["total"]["line"] = line
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


@pytest.mark.parametrize("selection_id", [True, False, 1.5, {}, [], "", "x" * 257])
def test_selection_ids_fail_closed_on_unsupported_types(selection_id):
    markets = _full_markets()
    markets["moneyline"]["away_selection_id"] = selection_id
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(markets=markets))


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_complete", 1),
        ("source_complete", "true"),
        ("exact_official_game_id_verified", 1),
        ("fuzzy_matching_used", 0),
        ("synthetic_game_id_used", 0),
        ("price_fabrication_used", 0),
    ],
)
def test_boolean_contract_fields_are_exact_booleans(field, value):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(**{field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("exact_official_game_id_verified", False),
        ("fuzzy_matching_used", True),
        ("synthetic_game_id_used", True),
        ("price_fabrication_used", True),
    ],
)
def test_identity_and_no_fabrication_guards_cannot_be_relaxed(field, value):
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(**_args(**{field: value}))


def test_wrong_step10_status_fails_closed():
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(
            **_args(step10_final_freeze_status="NOT_FROZEN")
        )


def test_wrong_step10_marker_fails_closed():
    with pytest.raises(MLBProviderContractError):
        build_market_provider_game_snapshot(
            **_args(step10_final_certification_marker="WRONG")
        )


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("data_type", "wrong"),
        ("schema_version", 2),
        ("record_key", "tampered"),
        ("provider_name", "Other"),
        ("market_count", 99),
        ("fully_priced", False),
        ("snapshot_sha256", "0" * 64),
        ("price_fabrication_used", True),
        ("fuzzy_matching_used", True),
    ],
)
def test_validator_rejects_tampered_snapshot(field, replacement):
    snapshot = build_market_provider_game_snapshot(**_args())
    snapshot[field] = replacement
    result = validate_market_provider_game_snapshot(snapshot)
    assert result["snapshot_valid"] is False
    assert result["failures"]


def test_validator_rejects_nested_market_tampering():
    snapshot = build_market_provider_game_snapshot(**_args())
    snapshot["markets"]["moneyline"]["away_odds"] = 999
    result = validate_market_provider_game_snapshot(snapshot)
    assert result["snapshot_valid"] is False


def test_snapshot_sha_changes_when_real_price_changes():
    first = build_market_provider_game_snapshot(**_args())
    markets = _full_markets()
    markets["moneyline"]["away_odds"] = 125
    second = build_market_provider_game_snapshot(**_args(markets=markets))
    assert first["snapshot_sha256"] != second["snapshot_sha256"]


def test_snapshot_does_not_accept_nan_or_infinite_values_anywhere_in_lines():
    for bad in (math.nan, math.inf, -math.inf):
        markets = _full_markets()
        markets["total"]["line"] = bad
        with pytest.raises(MLBProviderContractError):
            build_market_provider_game_snapshot(**_args(markets=markets))
