from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.collectors import mlb_event_player_identity as step19c
from sports_api.collectors import mlb_live_market_feed as step19b
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    build_market_provider_game_snapshot,
)
from sports_api.mlb_step19e_production_persistence_validation_v1 import (
    RESULT_DATA_TYPE as STEP19E_RESULT_DATA_TYPE,
)
from sports_api.mlb_step20a_end_to_end_certification_v1 import (
    CERTIFICATION_STATUS,
    DATA_TYPE,
    EXISTING_API_DATA_TYPE,
    EXISTING_CONSUMER_PATH,
    FINAL_CERTIFICATION_MARKER,
    MLBStep20AEndToEndCertificationError,
    SCHEMA_VERSION,
    STEP20A_BASE_MAIN_SHA,
    certification_manifest,
    certify_recovered_step19_to_existing_mlb_consumer,
)


def _official_slate(game_id: int = 777001):
    return {
        "sport": "MLB",
        "slate_date": "2026-09-02",
        "game_count": 1,
        "source": "MLB Stats API",
        "games": [
            {
                "game_pk": game_id,
                "game_date": "2026-09-02T23:10:00Z",
                "official_date": "2026-09-02",
                "status": "scheduled",
                "status_detail": "Scheduled",
                "away_team": {"id": 10, "name": "Away Club"},
                "home_team": {"id": 20, "name": "Home Club"},
                "doubleheader": False,
                "doubleheader_code": "N",
                "game_number": 1,
                "reschedule_date": None,
                "is_postponed": False,
                "is_cancelled": False,
            }
        ],
    }


def _markets(*, complete: bool = True):
    result = {
        "moneyline": {
            "market_id": "ml-1",
            "market_time_utc": None,
            "away_odds": -120,
            "home_odds": 104,
            "away_selection_id": "a",
            "home_selection_id": "h",
        }
    }
    if complete:
        result.update(
            {
                "run_line": {
                    "market_id": "rl-1",
                    "market_time_utc": None,
                    "away_line": -1.5,
                    "away_odds": 135,
                    "home_line": 1.5,
                    "home_odds": -155,
                    "away_selection_id": "ra",
                    "home_selection_id": "rh",
                },
                "total": {
                    "market_id": "tot-1",
                    "market_time_utc": None,
                    "line": 8.5,
                    "over_odds": -108,
                    "under_odds": -112,
                    "over_selection_id": "o",
                    "under_selection_id": "u",
                },
            }
        )
    return result


def _snapshot(
    *,
    provider_key: str = "fanduel",
    provider_name: str = "FanDuel",
    provider_event_id: str = "fd-100",
    game_id: int = 777001,
    complete: bool = True,
):
    return build_market_provider_game_snapshot(
        provider_key=provider_key,
        provider_name=provider_name,
        provider_event_id=provider_event_id,
        official_game_id=game_id,
        observed_at_utc="2026-09-02T20:00:01Z",
        source_collected_at_utc="2026-09-02T20:00:00Z",
        market_phase="PREGAME",
        transport="anonymous_public_get_only",
        source_payload_sha256="a" * 64,
        markets=_markets(complete=complete),
        source_complete=True,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )


def _feed(snapshot=None):
    snapshot = deepcopy(snapshot or _snapshot())
    return {
        "data_type": step19b.DATA_TYPE,
        "schema_version": step19b.SCHEMA_VERSION,
        "observed_at_utc": "2026-09-02T20:00:01Z",
        "game_market_snapshot_count": 1,
        "player_prop_count": 0,
        "successful_surface_count": 1,
        "enabled_surface_count": 1,
        "not_ready_surface_count": 0,
        "error_surface_count": 0,
        "rejected_record_count": 0,
        "game_market_snapshots": [snapshot],
        "player_props": [],
        "provider_surface_statuses": [],
        "rejected_records": [],
    }


def _recovered(*, snapshot=None):
    official = _official_slate()
    feed = _feed(snapshot)
    registry = step19c.build_mlb_event_player_identity_registry(
        official_slate=official,
        market_feed=feed,
    )
    reliability = {
        "fanduel": {
            "cooldown_until_utc": None,
            "cooldown_reason": None,
            "last_failure_kind": None,
            "last_failure_at_utc": None,
            "last_success_at_utc": "2026-09-02T20:00:01Z",
        }
    }
    reliable = {
        "market_feed": deepcopy(feed),
        "reliability_state": deepcopy(reliability),
    }
    envelope = {
        "official_slate": deepcopy(official),
        "reliable_market_collection": reliable,
        "identity_registry": deepcopy(registry),
    }
    return {
        "data_type": STEP19E_RESULT_DATA_TYPE,
        "schema_version": 1,
        "operation": "recover",
        "status": "recovered",
        "found": True,
        "checkpoint_version": 1,
        "checkpoint_id": "253d836d-9aad-5c57-ac61-75a52162a86c",
        "envelope_content_sha256": "b" * 64,
        "checkpoint_envelope": envelope,
        "official_slate_for_restart": deepcopy(official),
        "market_feed_for_restart": deepcopy(feed),
        "identity_registry_for_restart": deepcopy(registry),
        "reliability_state_for_restart": deepcopy(reliability),
        "production_runtime_wiring": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
    }


def _sync_feed(candidate):
    candidate["checkpoint_envelope"]["reliable_market_collection"]["market_feed"] = deepcopy(
        candidate["market_feed_for_restart"]
    )


def _sync_registry(candidate):
    candidate["checkpoint_envelope"]["identity_registry"] = deepcopy(
        candidate["identity_registry_for_restart"]
    )


def test_manifest_freezes_certification_only_boundary():
    manifest = certification_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["step20a_base_main_sha"] == STEP20A_BASE_MAIN_SHA
    assert manifest["certification_status"] == CERTIFICATION_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["existing_consumer_path"] == EXISTING_CONSUMER_PATH
    assert manifest["new_provider_calls_added_by_step20a"] is False
    assert manifest["production_runtime_wiring_added_by_step20a"] is False
    assert manifest["production_database_writes_enabled"] is False
    assert manifest["actionable_output_enabled"] is False
    assert manifest["wagering_enabled"] is False


def test_valid_recovered_chain_crosses_existing_consumer_seam():
    result = certify_recovered_step19_to_existing_mlb_consumer(_recovered())
    assert result["certification_status"] == "certified"
    assert result["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert result["consumer_api_path"] == "/api/v1/mlb/odds"
    assert result["consumer_api_data_type"] == EXISTING_API_DATA_TYPE
    assert result["official_game_count"] == 1
    assert result["market_game_snapshot_count"] == 1
    assert result["verified_event_identity_count"] == 1
    assert result["consumer_game_count"] == 1
    assert result["consumer_card_count"] == 1
    assert result["consumer_official_game_ids"] == [777001]


def test_existing_api_payload_preserves_official_teams_start_and_prices():
    result = certify_recovered_step19_to_existing_mlb_consumer(_recovered())
    game = result["consumer_payload"]["games"][0]
    card = result["consumer_cards"][0]
    assert game["official_game_id"] == 777001
    assert game["scheduled_start_utc"] == "2026-09-02T23:10:00Z"
    assert game["away_team"] == {"id": 10, "name": "Away Club"}
    assert game["home_team"] == {"id": 20, "name": "Home Club"}
    assert game["markets"]["moneyline"]["away_odds"] == -120
    assert card["matchup"] == "Away Club @ Home Club"
    assert card["moneyline"] == {"away": "-120", "home": "+104"}
    assert card["run_line"]["away_line"] == "-1.5"
    assert card["total"] == {"line": "8.5", "over": "-108", "under": "-112"}


def test_result_is_deep_copy_isolated_from_recovered_bundle():
    recovered = _recovered()
    result = certify_recovered_step19_to_existing_mlb_consumer(recovered)
    result["consumer_payload"]["games"][0]["away_team"]["name"] = "Mutated"
    assert recovered["official_slate_for_restart"]["games"][0]["away_team"]["name"] == "Away Club"


@pytest.mark.parametrize(
    "field,value",
    [
        ("production_runtime_wiring", True),
        ("model_probability_mutation", True),
        ("projection_mutation", True),
        ("actionable_output", True),
        ("wagering", True),
    ],
)
def test_recovered_safety_flags_fail_closed(field, value):
    recovered = _recovered()
    recovered[field] = value
    with pytest.raises(MLBStep20AEndToEndCertificationError, match=field):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_not_recovered_fails_closed():
    recovered = _recovered()
    recovered["status"] = "loaded"
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="recovery"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_wrong_step19e_result_contract_fails_closed():
    recovered = _recovered()
    recovered["data_type"] = "wrong"
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="Step19E result"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_restart_official_slate_copy_mismatch_fails_closed():
    recovered = _recovered()
    recovered["official_slate_for_restart"]["games"][0]["away_team"]["name"] = "Wrong"
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="official slate differs"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_restart_market_feed_copy_mismatch_fails_closed():
    recovered = _recovered()
    recovered["market_feed_for_restart"]["observed_at_utc"] = "2026-09-02T20:00:02Z"
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="market feed differs"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_restart_identity_registry_copy_mismatch_fails_closed():
    recovered = _recovered()
    recovered["identity_registry_for_restart"]["official_slate_date"] = "wrong"
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="identity registry differs"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_restart_reliability_state_copy_mismatch_fails_closed():
    recovered = _recovered()
    recovered["reliability_state_for_restart"]["fanduel"]["cooldown_reason"] = "changed"
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="reliability state differs"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_duplicate_official_game_id_fails_closed():
    recovered = _recovered()
    duplicate = deepcopy(recovered["official_slate_for_restart"]["games"][0])
    recovered["official_slate_for_restart"]["games"].append(duplicate)
    recovered["official_slate_for_restart"]["game_count"] = 2
    recovered["checkpoint_envelope"]["official_slate"] = deepcopy(
        recovered["official_slate_for_restart"]
    )
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="duplicate official game"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_market_feed_rejected_record_fails_closed():
    recovered = _recovered()
    recovered["market_feed_for_restart"]["rejected_record_count"] = 1
    _sync_feed(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="rejected records"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_market_feed_provider_error_fails_closed():
    recovered = _recovered()
    recovered["market_feed_for_restart"]["error_surface_count"] = 1
    _sync_feed(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="provider errors"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_market_feed_not_ready_surface_fails_closed():
    recovered = _recovered()
    recovered["market_feed_for_restart"]["not_ready_surface_count"] = 1
    _sync_feed(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="not-ready"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_tampered_step11_snapshot_fails_closed():
    recovered = _recovered()
    recovered["market_feed_for_restart"]["game_market_snapshots"][0]["fuzzy_matching_used"] = True
    _sync_feed(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="Step11A validation"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_identity_registry_incomplete_fails_closed():
    recovered = _recovered()
    recovered["identity_registry_for_restart"]["identity_complete_for_all_market_games"] = False
    _sync_registry(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="incomplete"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_identity_registry_rejected_event_fails_closed():
    recovered = _recovered()
    recovered["identity_registry_for_restart"]["rejected_event_identity_count"] = 1
    _sync_registry(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="rejected events"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_identity_registry_fuzzy_flag_fails_closed():
    recovered = _recovered()
    recovered["identity_registry_for_restart"]["fuzzy_matching_used"] = True
    _sync_registry(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="fuzzy_matching_used"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_identity_registry_price_fabrication_flag_fails_closed():
    recovered = _recovered()
    recovered["identity_registry_for_restart"]["price_fabrication_used"] = True
    _sync_registry(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="price_fabrication_used"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_event_identity_game_conflict_fails_closed():
    recovered = _recovered()
    recovered["identity_registry_for_restart"]["event_identities"][0]["official_game_id"] = 777099
    _sync_registry(recovered)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="does not match certified event identity"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_non_fanduel_only_feed_cannot_claim_existing_fanduel_consumer_certification():
    snapshot = _snapshot(
        provider_key="draftkings",
        provider_name="DraftKings",
        provider_event_id="dk-100",
    )
    recovered = _recovered(snapshot=snapshot)
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="no fully priced certified FanDuel"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_partial_fanduel_snapshot_cannot_be_presented_as_fully_priced():
    recovered = _recovered(snapshot=_snapshot(complete=False))
    with pytest.raises(MLBStep20AEndToEndCertificationError, match="no fully priced certified FanDuel"):
        certify_recovered_step19_to_existing_mlb_consumer(recovered)


def test_consumer_output_reports_zero_new_side_effects():
    result = certify_recovered_step19_to_existing_mlb_consumer(_recovered())
    assert result["provider_network_calls_added_by_step20a"] == 0
    assert result["database_reads_added_by_step20a"] == 0
    assert result["database_writes_added_by_step20a"] == 0
    assert result["production_runtime_wiring"] is False
    assert result["production_scheduler_mutation"] is False
    assert result["model_probability_mutation"] is False
    assert result["projection_mutation"] is False
    assert result["actionable_output"] is False
    assert result["wagering"] is False
    assert result["fuzzy_matching_used"] is False
    assert result["synthetic_game_id_used"] is False
    assert result["synthetic_player_id_used"] is False
    assert result["price_fabrication_used"] is False
