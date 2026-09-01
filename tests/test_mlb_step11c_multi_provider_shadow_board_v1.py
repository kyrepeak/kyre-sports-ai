from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    CONTRACT_STATUS as STEP11A_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11A_MARKER,
    SUPPORTED_CORE_MARKETS,
    build_market_provider_game_snapshot,
)
from sports_api.collectors.mlb_draftkings_provider import (
    ADAPTER_STATUS as STEP11B_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11B_MARKER,
)
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import (
    BOARD_STATUS,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MAX_INPUT_SNAPSHOTS,
    MLBMultiProviderShadowBoardError,
    PROVIDER_NAMES,
    SCHEMA_VERSION,
    STEP11C_BASE_MAIN_SHA,
    SUPPORTED_PROVIDERS,
    build_multi_provider_shadow_board,
    shadow_board_manifest,
    validate_multi_provider_shadow_board,
)


ASSEMBLED = "2026-09-01T17:40:00Z"


def _markets(*, partial: bool = False, tweak: int = 0):
    result = {
        "moneyline": {
            "market_id": f"ml-{tweak}",
            "market_time_utc": None,
            "away_odds": 110 + tweak,
            "home_odds": -130 - tweak,
            "away_selection_id": f"a-ml-{tweak}",
            "home_selection_id": f"h-ml-{tweak}",
        },
        "run_line": {
            "market_id": f"rl-{tweak}",
            "market_time_utc": None,
            "away_line": 1.5,
            "away_odds": -105,
            "home_line": -1.5,
            "home_odds": -115,
            "away_selection_id": f"a-rl-{tweak}",
            "home_selection_id": f"h-rl-{tweak}",
        },
        "total": {
            "market_id": f"tot-{tweak}",
            "market_time_utc": None,
            "line": 8.5,
            "over_odds": -110,
            "under_odds": -110,
            "over_selection_id": f"o-{tweak}",
            "under_selection_id": f"u-{tweak}",
        },
    }
    if partial:
        result.pop("total")
    return result


def _snapshot(
    provider: str,
    *,
    game_id: int = 999001,
    phase: str = "PREGAME",
    observed: str = "2026-09-01T17:30:00Z",
    partial: bool = False,
    tweak: int = 0,
    provider_name: str | None = None,
    provider_event_id: str | None = None,
):
    name = provider_name if provider_name is not None else PROVIDER_NAMES.get(
        provider, provider.title()
    )
    event_id = provider_event_id or f"{provider}-event-{game_id}-{phase.lower()}"
    payload_hash = hashlib.sha256(
        json.dumps(
            {
                "provider": provider,
                "game_id": game_id,
                "phase": phase,
                "observed": observed,
                "partial": partial,
                "tweak": tweak,
                "event": event_id,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return build_market_provider_game_snapshot(
        provider_key=provider,
        provider_name=name,
        provider_event_id=event_id,
        official_game_id=game_id,
        observed_at_utc=observed,
        source_collected_at_utc=observed,
        market_phase=phase,
        transport=f"{provider}_fixture",
        source_payload_sha256=payload_hash,
        markets=_markets(partial=partial, tweak=tweak),
        source_complete=True,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )


def _dual_board():
    return build_multi_provider_shadow_board(
        [_snapshot("fanduel"), _snapshot("draftkings")],
        assembled_at_utc=ASSEMBLED,
    )


def test_manifest_freezes_step11c_boundary():
    m = shadow_board_manifest()
    assert m["data_type"] == DATA_TYPE
    assert m["schema_version"] == SCHEMA_VERSION == 1
    assert m["step11c_base_main_sha"] == STEP11C_BASE_MAIN_SHA == (
        "05aa8b6299f6300146666bcbb1601158d0ce364d"
    )
    assert m["board_status"] == BOARD_STATUS
    assert m["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert m["step11a_contract_status_required"] == STEP11A_STATUS
    assert m["step11a_final_certification_marker_required"] == STEP11A_MARKER
    assert m["step11b_adapter_status_required"] == STEP11B_STATUS
    assert m["step11b_final_certification_marker_required"] == STEP11B_MARKER
    assert tuple(m["supported_providers"]) == SUPPORTED_PROVIDERS
    assert m["supported_provider_names"] == PROVIDER_NAMES
    assert tuple(m["supported_core_markets"]) == SUPPORTED_CORE_MARKETS


@pytest.mark.parametrize(
    "key",
    [
        "exact_official_game_id_only",
        "exact_record_duplicate_deduplication_allowed",
        "shadow_board_only",
    ],
)
def test_manifest_required_true_invariants(key):
    assert shadow_board_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "ambiguous_provider_slot_selection_allowed",
        "cross_provider_event_id_join_allowed",
        "team_name_join_allowed",
        "player_name_join_allowed",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "best_price_selection_enabled",
        "provider_consensus_enabled",
        "provider_failover_enabled",
        "provider_weighting_enabled",
        "network_io_added_by_step11c",
        "production_api_wiring_added_by_step11c",
        "production_runtime_wiring_added_by_step11c",
        "persistence_schema_changed_by_step11c",
        "production_database_writes_enabled",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ],
)
def test_manifest_forbidden_behaviors_stay_false(key):
    assert shadow_board_manifest()[key] is False


def test_manifest_preserves_all_prior_protected_invariants():
    m = shadow_board_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert m[key] is False


def test_manifest_returns_nested_copy_isolation():
    a = shadow_board_manifest()
    b = shadow_board_manifest()
    a["supported_providers"].append("bad")
    a["supported_provider_names"]["bad"] = "Bad"
    assert b["supported_providers"] == ["fanduel", "draftkings"]
    assert "bad" not in b["supported_provider_names"]


@pytest.mark.parametrize("provider", SUPPORTED_PROVIDERS)
def test_single_provider_board(provider):
    board = build_multi_provider_shadow_board(
        [_snapshot(provider)], assembled_at_utc=ASSEMBLED
    )
    assert board["data_type"] == DATA_TYPE
    assert board["provider_keys_present"] == [provider]
    assert board["input_snapshot_count"] == 1
    assert board["unique_snapshot_count"] == 1
    assert board["unique_game_count"] == 1
    assert board["game_phase_group_count"] == 1
    assert board["dual_provider_game_phase_group_count"] == 0
    group = board["game_phase_groups"][0]
    assert group["provider_keys"] == [provider]
    assert group["all_supported_providers_present"] is False


def test_dual_provider_board_groups_by_exact_gamepk_and_phase():
    board = _dual_board()
    assert board["provider_keys_present"] == ["fanduel", "draftkings"]
    assert board["provider_unique_counts"] == {"fanduel": 1, "draftkings": 1}
    assert board["game_phase_group_count"] == 1
    assert board["dual_provider_game_phase_group_count"] == 1
    group = board["game_phase_groups"][0]
    assert group["official_game_id"] == 999001
    assert group["market_phase"] == "PREGAME"
    assert group["provider_count"] == 2
    assert group["provider_keys"] == ["fanduel", "draftkings"]
    assert group["all_supported_providers_present"] is True
    assert group["market_overlap_count"] == 3


def test_provider_event_ids_do_not_need_to_match_cross_provider():
    fd = _snapshot("fanduel", provider_event_id="fd-xyz")
    dk = _snapshot("draftkings", provider_event_id="dk-completely-different")
    board = build_multi_provider_shadow_board([fd, dk], assembled_at_utc=ASSEMBLED)
    assert board["game_phase_group_count"] == 1
    providers = board["game_phase_groups"][0]["providers"]
    assert {p["provider_event_id"] for p in providers} == {
        "fd-xyz",
        "dk-completely-different",
    }
    assert board["cross_provider_event_id_join_used"] is False


def test_same_provider_event_id_on_different_gamepks_never_joins_games():
    a = _snapshot("fanduel", game_id=999001, provider_event_id="same-event")
    b = _snapshot("draftkings", game_id=999002, provider_event_id="same-event")
    board = build_multi_provider_shadow_board([a, b], assembled_at_utc=ASSEMBLED)
    assert board["unique_game_count"] == 2
    assert board["game_phase_group_count"] == 2
    assert [g["official_game_id"] for g in board["game_phase_groups"]] == [
        999001,
        999002,
    ]


def test_input_order_does_not_change_board():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    a = build_multi_provider_shadow_board([fd, dk], assembled_at_utc=ASSEMBLED)
    b = build_multi_provider_shadow_board([dk, fd], assembled_at_utc=ASSEMBLED)
    assert a == b


def test_exact_duplicate_is_deduplicated_for_board_views():
    fd = _snapshot("fanduel")
    board = build_multi_provider_shadow_board([fd, deepcopy(fd)], assembled_at_utc=ASSEMBLED)
    assert board["input_snapshot_count"] == 2
    assert board["unique_snapshot_count"] == 1
    assert board["exact_duplicate_count"] == 1
    assert board["provider_input_counts"]["fanduel"] == 2
    assert board["provider_unique_counts"]["fanduel"] == 1
    assert board["game_phase_groups"][0]["provider_count"] == 1


def test_duplicate_count_is_order_independent():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    a = build_multi_provider_shadow_board([fd, dk, fd], assembled_at_utc=ASSEMBLED)
    b = build_multi_provider_shadow_board([fd, fd, dk], assembled_at_utc=ASSEMBLED)
    assert a == b
    assert a["exact_duplicate_count"] == 1


def test_distinct_snapshots_for_same_current_provider_slot_fail_closed():
    a = _snapshot("fanduel", tweak=0)
    b = _snapshot("fanduel", tweak=1)
    with pytest.raises(MLBMultiProviderShadowBoardError, match="ambiguous"):
        build_multi_provider_shadow_board([a, b], assembled_at_utc=ASSEMBLED)


def test_same_provider_different_phases_are_separate_valid_slots():
    pre = _snapshot("fanduel", phase="PREGAME")
    live = _snapshot("fanduel", phase="IN_PLAY")
    board = build_multi_provider_shadow_board([pre, live], assembled_at_utc=ASSEMBLED)
    assert board["game_phase_group_count"] == 2
    assert [g["market_phase"] for g in board["game_phase_groups"]] == [
        "IN_PLAY",
        "PREGAME",
    ]


def test_same_provider_different_games_are_separate_valid_slots():
    a = _snapshot("fanduel", game_id=999001)
    b = _snapshot("fanduel", game_id=999002)
    board = build_multi_provider_shadow_board([a, b], assembled_at_utc=ASSEMBLED)
    assert board["unique_game_count"] == 2
    assert board["game_phase_group_count"] == 2


def test_group_order_is_gamepk_then_phase():
    rows = [
        _snapshot("fanduel", game_id=999002, phase="PREGAME"),
        _snapshot("fanduel", game_id=999001, phase="PREGAME"),
        _snapshot("draftkings", game_id=999001, phase="IN_PLAY"),
    ]
    board = build_multi_provider_shadow_board(rows, assembled_at_utc=ASSEMBLED)
    assert [
        (g["official_game_id"], g["market_phase"])
        for g in board["game_phase_groups"]
    ] == [(999001, "IN_PLAY"), (999001, "PREGAME"), (999002, "PREGAME")]


def test_provider_order_is_fixed_not_input_order():
    board = build_multi_provider_shadow_board(
        [_snapshot("draftkings"), _snapshot("fanduel")],
        assembled_at_utc=ASSEMBLED,
    )
    assert board["game_phase_groups"][0]["provider_keys"] == [
        "fanduel",
        "draftkings",
    ]


def test_market_views_follow_frozen_core_market_order():
    board = _dual_board()
    assert [m["market_name"] for m in board["game_phase_groups"][0]["market_views"]] == list(
        SUPPORTED_CORE_MARKETS
    )


def test_market_views_preserve_each_books_raw_contract_market():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    board = build_multi_provider_shadow_board([fd, dk], assembled_at_utc=ASSEMBLED)
    views = {
        row["market_name"]: row
        for row in board["game_phase_groups"][0]["market_views"]
    }
    fd_ml = next(
        row for row in views["moneyline"]["providers"] if row["provider_key"] == "fanduel"
    )
    dk_ml = next(
        row for row in views["moneyline"]["providers"] if row["provider_key"] == "draftkings"
    )
    assert fd_ml["market"] == fd["markets"]["moneyline"]
    assert dk_ml["market"] == dk["markets"]["moneyline"]


def test_partial_market_is_omitted_not_fabricated():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings", partial=True)
    board = build_multi_provider_shadow_board([fd, dk], assembled_at_utc=ASSEMBLED)
    group = board["game_phase_groups"][0]
    total = next(m for m in group["market_views"] if m["market_name"] == "total")
    assert total["provider_count"] == 1
    assert total["provider_keys"] == ["fanduel"]
    assert group["market_overlap_count"] == 2
    assert board["price_fabrication_used"] is False
    assert board["fallback_price_fabrication_used"] is False


def test_partial_provider_makes_all_present_fully_priced_false():
    board = build_multi_provider_shadow_board(
        [_snapshot("fanduel"), _snapshot("draftkings", partial=True)],
        assembled_at_utc=ASSEMBLED,
    )
    group = board["game_phase_groups"][0]
    assert group["fully_priced_provider_count"] == 1
    assert group["all_present_providers_fully_priced"] is False


def test_full_dual_provider_group_reports_both_fully_priced():
    group = _dual_board()["game_phase_groups"][0]
    assert group["fully_priced_provider_count"] == 2
    assert group["all_present_providers_fully_priced"] is True


def test_no_best_price_consensus_failover_or_weighting_fields_are_derived():
    board = _dual_board()
    assert board["best_price_selection_used"] is False
    assert board["provider_consensus_used"] is False
    assert board["provider_failover_used"] is False
    assert board["provider_weighting_used"] is False
    serialized = json.dumps(board, sort_keys=True)
    assert '"consensus_price"' not in serialized
    assert '"best_price"' not in serialized
    assert '"selected_provider"' not in serialized


def test_no_network_runtime_or_database_actions():
    board = _dual_board()
    assert board["network_io_performed"] is False
    assert board["production_runtime_wiring"] is False
    assert board["production_database_writes"] is False
    assert board["persisted_snapshot_as_model_input"] is False
    assert board["persisted_snapshot_as_sportsbook_input"] is False


def test_board_hash_is_deterministic():
    a = _dual_board()
    b = _dual_board()
    assert a["board_sha256"] == b["board_sha256"]
    assert a == b


def test_assembled_time_is_part_of_board_hash():
    rows = [_snapshot("fanduel"), _snapshot("draftkings")]
    a = build_multi_provider_shadow_board(rows, assembled_at_utc=ASSEMBLED)
    b = build_multi_provider_shadow_board(
        rows, assembled_at_utc="2026-09-01T17:41:00Z"
    )
    assert a["board_sha256"] != b["board_sha256"]


def test_input_snapshots_are_not_mutated():
    rows = [_snapshot("fanduel"), _snapshot("draftkings")]
    before = deepcopy(rows)
    build_multi_provider_shadow_board(rows, assembled_at_utc=ASSEMBLED)
    assert rows == before


def test_board_is_deep_copy_isolated_from_later_input_mutation():
    fd = _snapshot("fanduel")
    board = build_multi_provider_shadow_board([fd], assembled_at_utc=ASSEMBLED)
    expected = deepcopy(board)
    fd["markets"]["moneyline"]["away_odds"] = 999
    assert board == expected


def test_source_snapshot_list_is_sorted_and_preserves_exact_duplicates():
    fd = _snapshot("fanduel")
    dk = _snapshot("draftkings")
    board = build_multi_provider_shadow_board([dk, fd, deepcopy(fd)], assembled_at_utc=ASSEMBLED)
    assert [row["provider_key"] for row in board["source_snapshots"]] == [
        "fanduel",
        "fanduel",
        "draftkings",
    ]
    assert board["source_record_keys"][0] == board["source_record_keys"][1]


def test_valid_board_validates():
    validation = validate_multi_provider_shadow_board(_dual_board())
    assert validation == {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_valid": True,
        "failures": [],
    }


def test_validator_rebuild_does_not_mutate_board():
    board = _dual_board()
    before = deepcopy(board)
    validate_multi_provider_shadow_board(board)
    assert board == before


@pytest.mark.parametrize("value", [None, [], "bad", 123, True])
def test_validator_rejects_non_mapping(value):
    result = validate_multi_provider_shadow_board(value)
    assert result["board_valid"] is False
    assert result["failures"] == ["STEP11C_BOARD_NOT_MAPPING"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("board_sha256",), "0" * 64),
        (("provider_consensus_used",), True),
        (("provider_failover_used",), True),
        (("price_fabrication_used",), True),
        (("game_phase_group_count",), 99),
        (("provider_keys_present",), ["draftkings"]),
    ],
)
def test_validator_detects_top_level_tampering(path, value):
    board = _dual_board()
    board[path[0]] = value
    result = validate_multi_provider_shadow_board(board)
    assert result["board_valid"] is False
    assert "STEP11C_BOARD_EXACT_CONTRACT_MISMATCH" in result["failures"]


def test_validator_detects_derived_group_tampering():
    board = _dual_board()
    board["game_phase_groups"][0]["provider_count"] = 99
    result = validate_multi_provider_shadow_board(board)
    assert result["board_valid"] is False


def test_validator_detects_source_snapshot_tampering():
    board = _dual_board()
    board["source_snapshots"][0]["markets"]["moneyline"]["away_odds"] = 777
    result = validate_multi_provider_shadow_board(board)
    assert result["board_valid"] is False
    assert result["failures"][0].startswith("STEP11C_REBUILD_FAILED:")


def test_validator_detects_extra_top_level_key():
    board = _dual_board()
    board["unexpected"] = "nope"
    result = validate_multi_provider_shadow_board(board)
    assert result["board_valid"] is False
    assert "STEP11C_BOARD_EXACT_CONTRACT_MISMATCH" in result["failures"]


def test_unsupported_provider_fails_even_when_step11a_snapshot_is_valid():
    other = _snapshot("otherbook", provider_name="OtherBook")
    with pytest.raises(MLBMultiProviderShadowBoardError, match="unsupported provider_key"):
        build_multi_provider_shadow_board([other], assembled_at_utc=ASSEMBLED)


def test_supported_provider_name_must_match_certified_name():
    bad = _snapshot("fanduel", provider_name="Fan Duel")
    with pytest.raises(MLBMultiProviderShadowBoardError, match="provider_name mismatch"):
        build_multi_provider_shadow_board([bad], assembled_at_utc=ASSEMBLED)


@pytest.mark.parametrize("bad", [None, 1, "snapshot", [], True])
def test_non_mapping_source_snapshot_fails(bad):
    with pytest.raises(MLBMultiProviderShadowBoardError, match="mapping"):
        build_multi_provider_shadow_board([bad], assembled_at_utc=ASSEMBLED)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fuzzy_matching_used", True),
        ("synthetic_game_id_used", True),
        ("price_fabrication_used", True),
        ("exact_official_game_id_verified", False),
        ("source_complete", 1),
    ],
)
def test_tampered_step11a_invariants_fail_closed(field, value):
    row = _snapshot("fanduel")
    row[field] = value
    with pytest.raises(MLBMultiProviderShadowBoardError, match="invalid Step 11A"):
        build_multi_provider_shadow_board([row], assembled_at_utc=ASSEMBLED)


def test_future_source_snapshot_is_rejected():
    row = _snapshot("fanduel", observed="2026-09-01T17:41:00Z")
    with pytest.raises(MLBMultiProviderShadowBoardError, match="cannot be after"):
        build_multi_provider_shadow_board([row], assembled_at_utc=ASSEMBLED)


@pytest.mark.parametrize(
    "assembled",
    [
        "2026-09-01T17:40:00+00:00",
        "2026-09-01 17:40:00",
        "not-a-time",
        "",
        None,
    ],
)
def test_assembled_timestamp_must_be_strict_utc_z(assembled):
    with pytest.raises(MLBMultiProviderShadowBoardError):
        build_multi_provider_shadow_board(
            [_snapshot("fanduel")], assembled_at_utc=assembled
        )


def test_empty_source_list_rejected():
    with pytest.raises(MLBMultiProviderShadowBoardError, match="must not be empty"):
        build_multi_provider_shadow_board([], assembled_at_utc=ASSEMBLED)


@pytest.mark.parametrize("bad", ["abc", b"abc", 5, None, {"a": 1}])
def test_source_snapshots_must_be_sequence_not_scalar_or_mapping(bad):
    with pytest.raises(MLBMultiProviderShadowBoardError, match="sequence"):
        build_multi_provider_shadow_board(bad, assembled_at_utc=ASSEMBLED)


def test_input_snapshot_limit_is_enforced_before_duplicate_processing():
    row = _snapshot("fanduel")
    with pytest.raises(MLBMultiProviderShadowBoardError, match=str(MAX_INPUT_SNAPSHOTS)):
        build_multi_provider_shadow_board(
            [row] * (MAX_INPUT_SNAPSHOTS + 1),
            assembled_at_utc=ASSEMBLED,
        )


def test_canonical_z_normalizes_fractional_precision():
    board = build_multi_provider_shadow_board(
        [_snapshot("fanduel")],
        assembled_at_utc="2026-09-01T17:40:00.000000Z",
    )
    assert board["assembled_at_utc"] == "2026-09-01T17:40:00Z"


def test_cross_provider_market_views_only_use_exact_group_members():
    rows = [
        _snapshot("fanduel", game_id=999001),
        _snapshot("draftkings", game_id=999002),
    ]
    board = build_multi_provider_shadow_board(rows, assembled_at_utc=ASSEMBLED)
    for group in board["game_phase_groups"]:
        assert group["provider_count"] == 1
        assert group["market_overlap_count"] == 0
        for market in group["market_views"]:
            assert market["provider_count"] == 1
            assert market["cross_provider_overlap"] is False
