from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sports_api.collectors.mlb_draftkings_provider import MLBDraftKingsProviderNotReadyError
from sports_api.collectors.mlb_live_market_feed import (
    DATA_TYPE,
    FEED_STATUS,
    FINAL_CERTIFICATION_MARKER,
    MLBLiveMarketFeedError,
    STEP19B_BASE_MAIN_SHA,
    collect_live_mlb_market_feed,
    feed_manifest,
)
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    build_market_provider_game_snapshot,
    validate_market_provider_game_snapshot,
)

NOW = datetime(2026, 9, 2, 3, 30, tzinfo=timezone.utc)


def _fanduel_game(*, game_id: int = 1001, event_id: str = "fd-event-1") -> dict:
    return {
        "official_game_id": game_id,
        "sportsbook_event_id": event_id,
        "sportsbook_event_name": "Away Club @ Home Club",
        "official_schedule_match": "teams_exact",
        "scheduled_start_utc": "2026-09-02T23:10:00Z",
        "sportsbook_start_utc": "2026-09-02T23:10:00Z",
        "game_status": "Scheduled",
        "away_team": {"id": 10, "name": "Away Club"},
        "home_team": {"id": 20, "name": "Home Club"},
        "sportsbook": "FanDuel",
        "sportsbook_region": "NJ",
        "markets": {
            "moneyline": {
                "market_id": f"{event_id}-ml",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "away_odds": -120,
                "home_odds": 110,
                "away_selection_id": "a-ml",
                "home_selection_id": "h-ml",
            },
            "run_line": {
                "market_id": f"{event_id}-rl",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "away_line": 1.5,
                "away_odds": -105,
                "home_line": -1.5,
                "home_odds": -115,
                "away_selection_id": "a-rl",
                "home_selection_id": "h-rl",
            },
            "total": {
                "market_id": f"{event_id}-tot",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "line": 8.5,
                "over_odds": -110,
                "under_odds": -110,
                "over_selection_id": "o-tot",
                "under_selection_id": "u-tot",
            },
        },
        "market_availability": {"moneyline": True, "run_line": True, "total": True},
        "fully_priced": True,
    }


def _fanduel_game_collection(games: list[dict] | None = None) -> dict:
    rows = [_fanduel_game()] if games is None else games
    return {
        "data_type": "mlb_live_game_odds_snapshot_v1",
        "schema_version": 1,
        "collected_at_utc": "2026-09-02T03:29:00+00:00",
        "provider": "FanDuel",
        "games": rows,
        "rejected_events": [],
    }


def _fanduel_prop(*, game_id: int = 1001, player_id: int = 501, market_type: str = "player_hits", market_id: str = "fd-prop-1") -> dict:
    return {
        "official_game_id": game_id,
        "official_player_id": player_id,
        "player_name": "Example Player",
        "market_type": market_type,
        "line": 0.5,
        "over_odds": -125,
        "under_odds": -105,
        "sportsbook": "FanDuel",
        "source_event_id": "fd-event-1",
        "source_market_id": market_id,
    }


def _fanduel_prop_collection(props: list[dict] | None = None) -> dict:
    rows = [_fanduel_prop()] if props is None else props
    return {
        "data_type": "mlb_live_player_prop_snapshot_v1",
        "schema_version": 1,
        "collected_at_utc": "2026-09-02T03:29:00+00:00",
        "provider": "FanDuel",
        "props": rows,
        "rejected_prop_count": 0,
        "rejected_event_count": 0,
    }


def _draftkings_snapshot(*, game_id: int = 1002, event_id: str = "dk-event-1") -> dict:
    return build_market_provider_game_snapshot(
        provider_key="draftkings",
        provider_name="DraftKings",
        provider_event_id=event_id,
        official_game_id=game_id,
        observed_at_utc="2026-09-02T03:30:00Z",
        source_collected_at_utc="2026-09-02T03:29:00Z",
        market_phase="PREGAME",
        transport="anonymous_public_get_only_explicit_url",
        source_payload_sha256="a" * 64,
        markets={
            "moneyline": {
                "market_id": f"{event_id}-ml",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "away_odds": -115,
                "home_odds": 105,
                "away_selection_id": "dk-away",
                "home_selection_id": "dk-home",
            }
        },
        source_complete=True,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )


def _collect(**overrides):
    kwargs = {
        "now_utc": NOW,
        "fanduel_game_collector": lambda **_: _fanduel_game_collection(),
        "fanduel_prop_collector": lambda **_: _fanduel_prop_collection(),
        "draftkings_collector": lambda **_: {
            "snapshots": [_draftkings_snapshot()],
            "rejected_snapshot_count": 0,
        },
    }
    kwargs.update(overrides)
    return collect_live_mlb_market_feed(**kwargs)


def test_manifest_freezes_step19b_boundary():
    manifest = feed_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["step19b_base_main_sha"] == STEP19B_BASE_MAIN_SHA
    assert manifest["feed_status"] == FEED_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["real_sportsbook_network_reads_allowed"] is True
    assert manifest["new_identity_matching_added_by_step19b"] is False
    assert manifest["price_fabrication_allowed"] is False
    assert manifest["production_runtime_wiring_added_by_step19b"] is False
    assert manifest["production_database_writes_enabled"] is False
    assert manifest["model_probability_mutation_enabled"] is False
    assert manifest["actionable_output_enabled"] is False
    assert manifest["wagering_enabled"] is False


def test_collects_fanduel_game_odds_into_provider_neutral_snapshot():
    feed = _collect(include_fanduel_player_props=False, include_draftkings=False)
    assert feed["game_market_snapshot_count"] == 1
    snapshot = feed["game_market_snapshots"][0]
    assert snapshot["provider_key"] == "fanduel"
    assert snapshot["official_game_id"] == 1001
    assert snapshot["provider_event_id"] == "fd-event-1"
    assert snapshot["market_phase"] == "PREGAME"
    assert snapshot["markets"]["moneyline"]["away_odds"] == -120
    assert snapshot["markets"]["run_line"]["away_line"] == 1.5
    assert snapshot["markets"]["total"]["line"] == 8.5
    assert snapshot["price_fabrication_used"] is False
    assert snapshot["fuzzy_matching_used"] is False
    assert validate_market_provider_game_snapshot(snapshot)["snapshot_valid"] is True


def test_collects_exact_fanduel_player_prop_identity():
    feed = _collect(include_fanduel_game_odds=False, include_draftkings=False)
    assert feed["player_prop_count"] == 1
    prop = feed["player_props"][0]
    assert prop["provider_key"] == "fanduel"
    assert prop["official_game_id"] == 1001
    assert prop["official_player_id"] == 501
    assert prop["market_type"] == "player_hits"
    assert prop["line"] == 0.5
    assert prop["exact_official_player_id_verified"] is True
    assert prop["player_name_matching_used"] is False
    assert prop["fuzzy_matching_used"] is False
    assert prop["price_fabrication_used"] is False


def test_passes_valid_draftkings_step11a_snapshot_through():
    feed = _collect(include_fanduel_game_odds=False, include_fanduel_player_props=False)
    assert feed["game_market_snapshot_count"] == 1
    snapshot = feed["game_market_snapshots"][0]
    assert snapshot == _draftkings_snapshot()
    assert feed["providers_with_data"] == ["draftkings"]


def test_combines_fanduel_and_draftkings_without_consensus_or_price_mutation():
    feed = _collect()
    assert feed["game_market_snapshot_count"] == 2
    assert feed["player_prop_count"] == 1
    assert feed["providers_with_data"] == ["draftkings", "fanduel"]
    assert feed["live_market_data_present"] is True
    assert feed["price_fabrication_used"] is False
    assert feed["model_probability_mutation"] is False
    assert feed["projection_mutation"] is False
    assert feed["actionable_output"] is False
    assert feed["wagering"] is False


def test_draftkings_not_ready_does_not_poison_fanduel():
    def not_ready(**_):
        raise MLBDraftKingsProviderNotReadyError("not configured")

    feed = _collect(draftkings_collector=not_ready)
    assert feed["game_market_snapshot_count"] == 1
    assert feed["player_prop_count"] == 1
    assert feed["not_ready_surface_count"] == 1
    dk = next(row for row in feed["provider_surface_statuses"] if row["surface"] == "draftkings_game_odds")
    assert dk["status"] == "not_ready"


def test_one_provider_error_is_isolated_from_other_valid_surfaces():
    def broken(**_):
        raise RuntimeError("upstream exploded")

    feed = _collect(fanduel_game_collector=broken)
    assert feed["error_surface_count"] == 1
    assert feed["game_market_snapshot_count"] == 1  # DraftKings remains valid.
    assert feed["player_prop_count"] == 1
    assert feed["live_market_data_present"] is True


def test_malformed_fanduel_game_is_rejected_without_fabrication():
    bad = _fanduel_game()
    bad["official_game_id"] = None
    feed = _collect(
        fanduel_game_collector=lambda **_: _fanduel_game_collection([bad]),
        include_fanduel_player_props=False,
        include_draftkings=False,
    )
    assert feed["game_market_snapshot_count"] == 0
    assert feed["rejected_record_count"] == 1
    assert "official_game_id" in feed["rejected_records"][0]["reason"]
    assert feed["live_market_data_present"] is False


def test_malformed_fanduel_prop_is_rejected_without_name_fallback():
    bad = _fanduel_prop()
    bad["official_player_id"] = None
    feed = _collect(
        fanduel_prop_collector=lambda **_: _fanduel_prop_collection([bad]),
        include_fanduel_game_odds=False,
        include_draftkings=False,
    )
    assert feed["player_prop_count"] == 0
    assert feed["rejected_record_count"] == 1
    assert "official_player_id" in feed["rejected_records"][0]["reason"]


def test_invalid_draftkings_snapshot_is_rejected_not_repaired():
    bad = _draftkings_snapshot()
    bad["markets"]["moneyline"]["away_odds"] = -99
    feed = _collect(
        include_fanduel_game_odds=False,
        include_fanduel_player_props=False,
        draftkings_collector=lambda **_: {"snapshots": [bad], "rejected_snapshot_count": 0},
    )
    assert feed["game_market_snapshot_count"] == 0
    assert feed["rejected_record_count"] == 1
    assert "step11a_validation_failed" in feed["rejected_records"][0]["reason"]


def test_duplicate_game_identity_fails_closed_for_that_identity():
    game = _fanduel_game()
    feed = _collect(
        fanduel_game_collector=lambda **_: _fanduel_game_collection([game, dict(game)]),
        include_fanduel_player_props=False,
        include_draftkings=False,
    )
    assert feed["game_market_snapshot_count"] == 0
    assert feed["rejected_record_count"] == 1
    assert feed["rejected_records"][0]["kind"] == "duplicate_game_market_identity"


def test_duplicate_player_prop_identity_fails_closed_for_that_identity():
    first = _fanduel_prop(market_id="m1")
    second = _fanduel_prop(market_id="m2")
    feed = _collect(
        fanduel_prop_collector=lambda **_: _fanduel_prop_collection([first, second]),
        include_fanduel_game_odds=False,
        include_draftkings=False,
    )
    assert feed["player_prop_count"] == 0
    assert feed["rejected_record_count"] == 1
    assert feed["rejected_records"][0]["kind"] == "duplicate_player_prop_identity"


def test_empty_successful_surfaces_are_valid_empty_feed():
    feed = _collect(
        fanduel_game_collector=lambda **_: _fanduel_game_collection([]),
        fanduel_prop_collector=lambda **_: _fanduel_prop_collection([]),
        include_draftkings=False,
    )
    assert feed["successful_surface_count"] == 2
    assert feed["game_market_snapshot_count"] == 0
    assert feed["player_prop_count"] == 0
    assert feed["live_market_data_present"] is False
    assert feed["error_surface_count"] == 0


def test_all_surfaces_can_be_disabled_without_network_or_output():
    feed = collect_live_mlb_market_feed(
        now_utc=NOW,
        include_fanduel_game_odds=False,
        include_fanduel_player_props=False,
        include_draftkings=False,
    )
    assert feed["enabled_surface_count"] == 0
    assert feed["provider_surface_statuses"] == []
    assert feed["game_market_snapshots"] == []
    assert feed["player_props"] == []
    assert feed["live_market_data_present"] is False
    assert feed["wagering"] is False


def test_naive_now_fails_closed():
    with pytest.raises(MLBLiveMarketFeedError, match="timezone-aware"):
        collect_live_mlb_market_feed(
            now_utc=datetime(2026, 9, 2, 3, 30),
            include_fanduel_game_odds=False,
            include_fanduel_player_props=False,
            include_draftkings=False,
        )


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "3"])
def test_invalid_max_events_fails_closed(value):
    with pytest.raises(MLBLiveMarketFeedError, match="max_events"):
        collect_live_mlb_market_feed(
            now_utc=NOW,
            max_events=value,
            include_fanduel_game_odds=False,
            include_fanduel_player_props=False,
            include_draftkings=False,
        )


def test_non_boolean_include_flag_fails_closed():
    with pytest.raises(MLBLiveMarketFeedError, match="include_draftkings"):
        collect_live_mlb_market_feed(
            now_utc=NOW,
            include_fanduel_game_odds=False,
            include_fanduel_player_props=False,
            include_draftkings="yes",
        )


def test_draftkings_phase_cannot_escape_pregame_boundary():
    with pytest.raises(MLBLiveMarketFeedError, match="PREGAME"):
        _collect(
            include_fanduel_game_odds=False,
            include_fanduel_player_props=False,
            draftkings_kwargs={"market_phase": "IN_PLAY"},
        )


def test_output_order_is_stable_by_game_then_provider():
    fd = [_fanduel_game(game_id=2002, event_id="fd-2"), _fanduel_game(game_id=1001, event_id="fd-1")]
    dk = [_draftkings_snapshot(game_id=1500, event_id="dk-15")]
    feed = _collect(
        fanduel_game_collector=lambda **_: _fanduel_game_collection(fd),
        fanduel_prop_collector=lambda **_: _fanduel_prop_collection([]),
        draftkings_collector=lambda **_: {"snapshots": dk, "rejected_snapshot_count": 0},
    )
    assert [(row["official_game_id"], row["provider_key"]) for row in feed["game_market_snapshots"]] == [
        (1001, "fanduel"),
        (1500, "draftkings"),
        (2002, "fanduel"),
    ]


def test_provider_status_counts_are_exact():
    feed = _collect()
    assert feed["enabled_surface_count"] == 3
    assert feed["successful_surface_count"] == 3
    assert feed["not_ready_surface_count"] == 0
    assert feed["error_surface_count"] == 0
    assert {row["surface"] for row in feed["provider_surface_statuses"]} == {
        "fanduel_game_odds",
        "fanduel_player_props",
        "draftkings_game_odds",
    }
