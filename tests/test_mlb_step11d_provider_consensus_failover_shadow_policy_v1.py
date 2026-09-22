from copy import deepcopy
import hashlib

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import build_market_provider_game_snapshot
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import (
    BOARD_STATUS as STEP11C_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11C_MARKER,
    build_multi_provider_shadow_board,
)
from sports_api.mlb_step11d_provider_consensus_failover_shadow_policy_v1 import (
    CONSENSUS_METHOD,
    DATA_TYPE,
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_MAX_AGE_SECONDS,
    DEFAULT_PRIMARY_PROVIDER,
    FINAL_CERTIFICATION_MARKER,
    MAX_MAX_AGE_SECONDS,
    POLICY_STATUS,
    SCHEMA_VERSION,
    STEP11D_BASE_MAIN_SHA,
    MLBProviderConsensusFailoverShadowPolicyError,
    build_provider_consensus_failover_shadow_policy,
    policy_manifest,
    validate_provider_consensus_failover_shadow_policy,
)

BASE_OBSERVED = "2026-09-01T12:00:00Z"
ASSEMBLED = "2026-09-01T12:00:30Z"
EVALUATED = "2026-09-01T12:01:00Z"
GAMEPK = 999001


def _markets(provider: str, *, run_line=1.5, total_line=8.5, complete=True):
    prefix = "fd" if provider == "fanduel" else "dk"
    values = {
        "moneyline": {
            "market_id": f"{prefix}-ml",
            "market_time_utc": None,
            "away_odds": 110 if provider == "fanduel" else 115,
            "home_odds": -130 if provider == "fanduel" else -135,
            "away_selection_id": f"{prefix}-a1",
            "home_selection_id": f"{prefix}-h1",
        },
        "run_line": {
            "market_id": f"{prefix}-rl",
            "market_time_utc": None,
            "away_line": run_line,
            "away_odds": -105 if provider == "fanduel" else -110,
            "home_line": -run_line,
            "home_odds": -115 if provider == "fanduel" else -110,
            "away_selection_id": f"{prefix}-a2",
            "home_selection_id": f"{prefix}-h2",
        },
        "total": {
            "market_id": f"{prefix}-tot",
            "market_time_utc": None,
            "line": total_line,
            "over_odds": -110 if provider == "fanduel" else -105,
            "under_odds": -110 if provider == "fanduel" else -115,
            "over_selection_id": f"{prefix}-o",
            "under_selection_id": f"{prefix}-u",
        },
    }
    if complete is True:
        return values
    return {"moneyline": values["moneyline"]}


def _snapshot(
    provider: str,
    *,
    observed=BASE_OBSERVED,
    gamepk=GAMEPK,
    phase="PREGAME",
    run_line=1.5,
    total_line=8.5,
    complete_markets=True,
    source_complete=True,
):
    return build_market_provider_game_snapshot(
        provider_key=provider,
        provider_name="FanDuel" if provider == "fanduel" else "DraftKings",
        provider_event_id=f"{provider}-event-{gamepk}",
        official_game_id=gamepk,
        observed_at_utc=observed,
        source_collected_at_utc=observed,
        market_phase=phase,
        transport="test_fixture",
        source_payload_sha256=hashlib.sha256(
            f"{provider}:{observed}:{gamepk}:{phase}:{run_line}:{total_line}:{complete_markets}".encode()
        ).hexdigest(),
        markets=_markets(
            provider,
            run_line=run_line,
            total_line=total_line,
            complete=complete_markets,
        ),
        source_complete=source_complete,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )


def _board(snapshots=None, *, assembled=ASSEMBLED):
    if snapshots is None:
        snapshots = [_snapshot("fanduel"), _snapshot("draftkings")]
    return build_multi_provider_shadow_board(snapshots, assembled_at_utc=assembled)


def _policy(board=None, **kwargs):
    return build_provider_consensus_failover_shadow_policy(
        board or _board(),
        evaluated_at_utc=kwargs.pop("evaluated_at_utc", EVALUATED),
        **kwargs,
    )


def _market(policy, name):
    return next(row for row in policy["groups"][0]["markets"] if row["market_name"] == name)


def test_manifest_identity_and_prerequisites():
    m = policy_manifest()
    assert m["data_type"] == DATA_TYPE
    assert m["schema_version"] == SCHEMA_VERSION == 1
    assert m["step11d_base_main_sha"] == STEP11D_BASE_MAIN_SHA
    assert m["policy_status"] == POLICY_STATUS
    assert m["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert m["step11c_board_status_required"] == STEP11C_STATUS
    assert m["step11c_final_certification_marker_required"] == STEP11C_MARKER


def test_manifest_route_defaults_and_consensus_method():
    m = policy_manifest()
    assert m["primary_provider"] == DEFAULT_PRIMARY_PROVIDER == "fanduel"
    assert m["fallback_provider"] == DEFAULT_FALLBACK_PROVIDER == "draftkings"
    assert m["default_max_age_seconds"] == DEFAULT_MAX_AGE_SECONDS
    assert m["consensus_method"] == CONSENSUS_METHOD


@pytest.mark.parametrize(
    "key",
    [
        "freshness_required_for_shadow_route",
        "source_complete_required_for_shadow_route",
        "same_official_game_id_required",
        "same_market_phase_required",
        "same_line_required_for_spread_total_consensus",
        "two_provider_consensus_required",
        "shadow_consensus_evaluation_enabled",
        "shadow_failover_routing_enabled",
    ],
)
def test_manifest_required_true_flags(key):
    assert policy_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "network_io_added_by_step11d",
        "production_api_wiring_added_by_step11d",
        "production_runtime_wiring_added_by_step11d",
        "persistence_schema_changed_by_step11d",
        "production_database_writes_enabled",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "team_name_join_allowed",
        "player_name_join_allowed",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ],
)
def test_manifest_required_false_flags(key):
    assert policy_manifest()[key] is False


def test_all_prior_protected_invariants_remain_false():
    m = policy_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert m[key] is False


def test_dual_provider_policy_is_valid_and_deterministic():
    p1 = _policy()
    p2 = _policy()
    assert p1 == p2
    assert validate_provider_consensus_failover_shadow_policy(p1)["policy_valid"] is True


def test_policy_counts_three_consensus_ready_markets():
    p = _policy()
    assert p["group_count"] == 1
    assert p["consensus_ready_market_count"] == 3
    assert p["shadow_failover_candidate_count"] == 0
    assert p["stale_provider_slot_count"] == 0


@pytest.mark.parametrize("market_name", ["moneyline", "run_line", "total"])
def test_primary_route_is_fanduel_when_both_are_fresh(market_name):
    market = _market(_policy(), market_name)
    assert market["available_provider_keys"] == ["fanduel", "draftkings"]
    assert market["shadow_route_provider"] == "fanduel"
    assert market["shadow_route_reason"] == "PRIMARY_AVAILABLE"
    assert market["shadow_failover_candidate"] is False
    assert market["production_route_changed"] is False


@pytest.mark.parametrize("market_name", ["moneyline", "run_line", "total"])
def test_two_provider_consensus_is_ready(market_name):
    consensus = _market(_policy(), market_name)["consensus"]
    assert consensus["available"] is True
    assert consensus["status"] == "TWO_PROVIDER_CONSENSUS_READY"
    assert consensus["method"] == CONSENSUS_METHOD
    assert consensus["provider_keys"] == ["fanduel", "draftkings"]


def test_moneyline_consensus_probabilities_sum_to_one():
    value = _market(_policy(), "moneyline")["consensus"]["consensus"]
    assert value["away_no_vig_probability"] + value["home_no_vig_probability"] == pytest.approx(1.0)


def test_run_line_consensus_probabilities_sum_to_one_and_line_preserved():
    value = _market(_policy(), "run_line")["consensus"]["consensus"]
    assert value["away_line"] == 1.5
    assert value["home_line"] == -1.5
    assert value["away_no_vig_probability"] + value["home_no_vig_probability"] == pytest.approx(1.0)


def test_total_consensus_probabilities_sum_to_one_and_line_preserved():
    value = _market(_policy(), "total")["consensus"]["consensus"]
    assert value["line"] == 8.5
    assert value["over_no_vig_probability"] + value["under_no_vig_probability"] == pytest.approx(1.0)


def test_run_line_mismatch_fails_closed_without_consensus():
    board = _board([
        _snapshot("fanduel", run_line=1.5),
        _snapshot("draftkings", run_line=2.5),
    ])
    c = _market(_policy(board), "run_line")["consensus"]
    assert c["available"] is False
    assert c["status"] == "LINE_MISMATCH"
    assert c["consensus"] is None
    assert c["provider_lines"]["fanduel"]["away_line"] == 1.5
    assert c["provider_lines"]["draftkings"]["away_line"] == 2.5


def test_total_line_mismatch_fails_closed_without_consensus():
    board = _board([
        _snapshot("fanduel", total_line=8.5),
        _snapshot("draftkings", total_line=9.0),
    ])
    c = _market(_policy(board), "total")["consensus"]
    assert c["available"] is False
    assert c["status"] == "LINE_MISMATCH"
    assert c["consensus"] is None


def test_moneyline_does_not_require_line_signature():
    assert _market(_policy(), "moneyline")["consensus"]["available"] is True


def test_stale_primary_routes_to_fresh_fallback_in_shadow_only():
    old = "2026-09-01T11:50:00Z"
    board = _board(
        [_snapshot("fanduel", observed=old), _snapshot("draftkings")],
        assembled=ASSEMBLED,
    )
    p = _policy(board, max_age_seconds=120)
    for market_name in ("moneyline", "run_line", "total"):
        market = _market(p, market_name)
        assert market["shadow_route_provider"] == "draftkings"
        assert market["shadow_route_reason"] == "PRIMARY_UNAVAILABLE_FALLBACK_AVAILABLE"
        assert market["shadow_failover_candidate"] is True
        assert market["production_route_changed"] is False
    assert p["shadow_failover_candidate_count"] == 3
    assert p["production_provider_failover_used"] is False


def test_stale_fallback_keeps_fresh_primary():
    old = "2026-09-01T11:50:00Z"
    board = _board(
        [_snapshot("fanduel"), _snapshot("draftkings", observed=old)],
        assembled=ASSEMBLED,
    )
    p = _policy(board, max_age_seconds=120)
    assert p["stale_provider_slot_count"] == 1
    assert p["shadow_failover_candidate_count"] == 0
    assert _market(p, "moneyline")["shadow_route_provider"] == "fanduel"


def test_both_stale_produces_no_route_and_no_consensus():
    old = "2026-09-01T11:50:00Z"
    board = _board(
        [_snapshot("fanduel", observed=old), _snapshot("draftkings", observed=old)],
        assembled=ASSEMBLED,
    )
    p = _policy(board, max_age_seconds=120)
    for market_name in ("moneyline", "run_line", "total"):
        market = _market(p, market_name)
        assert market["shadow_route_provider"] is None
        assert market["shadow_route_reason"] == "NO_ELIGIBLE_PROVIDER"
        assert market["consensus"]["status"] == "NO_AVAILABLE_PROVIDER"


def test_source_incomplete_primary_routes_to_fallback():
    board = _board([
        _snapshot("fanduel", source_complete=False),
        _snapshot("draftkings"),
    ])
    p = _policy(board)
    assert _market(p, "moneyline")["shadow_route_provider"] == "draftkings"


def test_single_primary_provider_routes_primary_but_has_no_consensus():
    p = _policy(_board([_snapshot("fanduel")]))
    market = _market(p, "moneyline")
    assert market["shadow_route_provider"] == "fanduel"
    assert market["consensus"]["status"] == "INSUFFICIENT_PROVIDERS"


def test_single_fallback_provider_is_shadow_failover_candidate():
    p = _policy(_board([_snapshot("draftkings")]))
    market = _market(p, "moneyline")
    assert market["shadow_route_provider"] == "draftkings"
    assert market["shadow_failover_candidate"] is True


def test_missing_market_never_gets_fabricated():
    board = _board([
        _snapshot("fanduel", complete_markets=False),
        _snapshot("draftkings", complete_markets=False),
    ])
    p = _policy(board)
    assert _market(p, "moneyline")["consensus"]["available"] is True
    for market_name in ("run_line", "total"):
        market = _market(p, market_name)
        assert market["available_provider_count"] == 0
        assert market["shadow_route_provider"] is None
        assert market["consensus"]["consensus"] is None
    assert p["price_fabrication_used"] is False


def test_primary_can_be_explicitly_reversed_for_shadow_evaluation():
    p = _policy(primary_provider="draftkings", fallback_provider="fanduel")
    assert p["primary_provider"] == "draftkings"
    assert _market(p, "moneyline")["shadow_route_provider"] == "draftkings"


@pytest.mark.parametrize("value", [True, False, 0, -1, 3601, 1.5, "180", None])
def test_invalid_max_age_fails_closed(value):
    with pytest.raises(MLBProviderConsensusFailoverShadowPolicyError):
        _policy(max_age_seconds=value)


@pytest.mark.parametrize("primary,fallback", [
    ("bad", "draftkings"),
    ("fanduel", "bad"),
    ("fanduel", "fanduel"),
    ("draftkings", "draftkings"),
])
def test_invalid_provider_routes_fail_closed(primary, fallback):
    with pytest.raises(MLBProviderConsensusFailoverShadowPolicyError):
        _policy(primary_provider=primary, fallback_provider=fallback)


@pytest.mark.parametrize("value", [
    "2026-09-01T12:01:00",
    "2026-09-01T12:01:00+00:00",
    "not-a-time",
    "",
    None,
])
def test_invalid_evaluated_timestamp_fails_closed(value):
    with pytest.raises(MLBProviderConsensusFailoverShadowPolicyError):
        _policy(evaluated_at_utc=value)


def test_evaluated_time_cannot_precede_board_assembly():
    with pytest.raises(MLBProviderConsensusFailoverShadowPolicyError):
        _policy(evaluated_at_utc="2026-09-01T12:00:00Z")


def test_provider_observation_cannot_be_in_future_of_evaluation():
    future = "2026-09-01T12:02:00Z"
    board = _board(
        [_snapshot("fanduel", observed=future), _snapshot("draftkings", observed=future)],
        assembled=future,
    )
    with pytest.raises(MLBProviderConsensusFailoverShadowPolicyError):
        _policy(board, evaluated_at_utc="2026-09-01T12:01:00Z")


def test_invalid_step11c_board_fails_closed():
    board = _board()
    board["board_sha256"] = "0" * 64
    with pytest.raises(MLBProviderConsensusFailoverShadowPolicyError):
        _policy(board)


def test_validator_rejects_non_mapping():
    result = validate_provider_consensus_failover_shadow_policy(None)
    assert result["policy_valid"] is False
    assert result["failures"] == ["STEP11D_POLICY_NOT_MAPPING"]


@pytest.mark.parametrize("field,value", [
    ("best_price_selection_used", True),
    ("provider_weighting_used", True),
    ("production_provider_consensus_used", True),
    ("production_provider_failover_used", True),
    ("price_fabrication_used", True),
    ("fallback_price_fabrication_used", True),
    ("network_io_performed", True),
    ("production_runtime_wiring", True),
    ("production_database_writes", True),
    ("persisted_snapshot_as_model_input", True),
    ("persisted_snapshot_as_sportsbook_input", True),
])
def test_validator_rejects_relaxed_safety_boundary(field, value):
    p = _policy()
    p[field] = value
    result = validate_provider_consensus_failover_shadow_policy(p)
    assert result["policy_valid"] is False
    assert result["failures"] == ["STEP11D_POLICY_EXACT_CONTRACT_MISMATCH"]


@pytest.mark.parametrize("field", [
    "policy_sha256",
    "source_board_sha256",
    "consensus_ready_market_count",
    "shadow_failover_candidate_count",
    "stale_provider_slot_count",
])
def test_validator_rejects_tampering(field):
    p = _policy()
    if isinstance(p[field], int):
        p[field] += 1
    else:
        p[field] = "0" * 64
    assert validate_provider_consensus_failover_shadow_policy(p)["policy_valid"] is False


def test_validator_is_non_mutating():
    p = _policy()
    original = deepcopy(p)
    assert validate_provider_consensus_failover_shadow_policy(p)["policy_valid"] is True
    assert p == original


def test_builder_does_not_mutate_source_board():
    board = _board()
    original = deepcopy(board)
    _policy(board)
    assert board == original


def test_result_copies_source_board():
    board = _board()
    p = _policy(board)
    board["provider_keys_present"].clear()
    assert p["source_board"]["provider_keys_present"] == ["fanduel", "draftkings"]


def test_exact_boundary_flags_remain_false_in_result():
    p = _policy()
    for key in [
        "best_price_selection_used",
        "provider_weighting_used",
        "production_provider_consensus_used",
        "production_provider_failover_used",
        "price_fabrication_used",
        "fallback_price_fabrication_used",
        "network_io_performed",
        "production_runtime_wiring",
        "production_database_writes",
        "persisted_snapshot_as_model_input",
        "persisted_snapshot_as_sportsbook_input",
    ]:
        assert p[key] is False


def test_shadow_evaluation_flags_are_true():
    p = _policy()
    assert p["shadow_consensus_evaluation_used"] is True
    assert p["shadow_failover_policy_evaluated"] is True


def test_policy_hash_changes_when_evaluation_time_changes():
    p1 = _policy()
    p2 = _policy(evaluated_at_utc="2026-09-01T12:01:01Z")
    assert p1["policy_sha256"] != p2["policy_sha256"]


def test_policy_hash_is_64_lower_hex():
    value = _policy()["policy_sha256"]
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def test_max_age_upper_bound_is_accepted():
    p = _policy(max_age_seconds=MAX_MAX_AGE_SECONDS)
    assert p["max_age_seconds"] == MAX_MAX_AGE_SECONDS


def test_exact_freshness_boundary_is_eligible():
    board = _board([
        _snapshot("fanduel", observed="2026-09-01T11:58:00Z"),
        _snapshot("draftkings", observed="2026-09-01T11:58:00Z"),
    ])
    p = _policy(board, max_age_seconds=180)
    assert all(row["fresh"] for row in p["groups"][0]["provider_health"])


def test_one_microsecond_past_freshness_boundary_is_stale():
    observed = "2026-09-01T11:57:59.999999Z"
    board = _board([
        _snapshot("fanduel", observed=observed),
        _snapshot("draftkings", observed=observed),
    ])
    p = _policy(board, max_age_seconds=180)
    assert all(not row["fresh"] for row in p["groups"][0]["provider_health"])


def test_multiple_game_groups_remain_exactly_separate():
    snapshots = [
        _snapshot("fanduel", gamepk=999001),
        _snapshot("draftkings", gamepk=999001),
        _snapshot("fanduel", gamepk=999002),
        _snapshot("draftkings", gamepk=999002),
    ]
    p = _policy(_board(snapshots))
    assert p["group_count"] == 2
    assert [row["official_game_id"] for row in p["groups"]] == [999001, 999002]


def test_pregame_and_inplay_groups_remain_separate():
    snapshots = [
        _snapshot("fanduel", phase="PREGAME"),
        _snapshot("draftkings", phase="PREGAME"),
        _snapshot("fanduel", phase="IN_PLAY"),
        _snapshot("draftkings", phase="IN_PLAY"),
    ]
    p = _policy(_board(snapshots))
    assert p["group_count"] == 2
    assert [row["market_phase"] for row in p["groups"]] == ["IN_PLAY", "PREGAME"]


def test_market_objects_are_preserved_not_best_price_rewritten():
    board = _board()
    p = _policy(board)
    fd_original = board["game_phase_groups"][0]["providers"][0]["markets"]["moneyline"]
    fd_policy = _market(p, "moneyline")
    fd_candidate = next(row for row in fd_policy["available_provider_keys"] if row == "fanduel")
    assert fd_candidate == "fanduel"
    assert fd_original["away_odds"] == 110


def test_source_board_hash_is_exact_step11c_hash():
    board = _board()
    p = _policy(board)
    assert p["source_board_sha256"] == board["board_sha256"]
