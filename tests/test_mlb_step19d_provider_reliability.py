from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sports_api.collectors.mlb_draftkings_provider import (
    MLBDraftKingsProviderNotReadyError,
)
from sports_api.collectors.mlb_provider_reliability import (
    DATA_TYPE,
    DEFAULT_MAX_ATTEMPTS,
    FINAL_CERTIFICATION_MARKER,
    RELIABILITY_STATUS,
    SCHEMA_VERSION,
    STEP19D_BASE_MAIN_SHA,
    MLBProviderReliabilityError,
    collect_reliable_mlb_market_feed,
    reliability_manifest,
)
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    build_market_provider_game_snapshot,
)

NOW = datetime(2026, 9, 2, 4, 15, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


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


def _fd_game_collection(
    *,
    collected_at: datetime = NOW,
    games: list[dict] | None = None,
) -> dict:
    return {
        "data_type": "mlb_live_game_odds_snapshot_v1",
        "schema_version": 1,
        "collected_at_utc": _iso(collected_at),
        "provider": "FanDuel",
        "games": [_fanduel_game()] if games is None else games,
        "rejected_events": [],
    }


def _fanduel_prop() -> dict:
    return {
        "official_game_id": 1001,
        "official_player_id": 501,
        "player_name": "Example Player",
        "market_type": "player_hits",
        "line": 0.5,
        "over_odds": -125,
        "under_odds": -105,
        "sportsbook": "FanDuel",
        "source_event_id": "fd-event-1",
        "source_market_id": "fd-prop-1",
    }


def _fd_prop_collection(*, collected_at: datetime = NOW) -> dict:
    return {
        "data_type": "mlb_live_player_prop_snapshot_v1",
        "schema_version": 1,
        "collected_at_utc": _iso(collected_at),
        "provider": "FanDuel",
        "props": [_fanduel_prop()],
        "rejected_prop_count": 0,
        "rejected_event_count": 0,
    }


def _dk_snapshot() -> dict:
    return build_market_provider_game_snapshot(
        provider_key="draftkings",
        provider_name="DraftKings",
        provider_event_id="dk-event-1",
        official_game_id=1002,
        observed_at_utc="2026-09-02T04:15:00Z",
        source_collected_at_utc="2026-09-02T04:14:30Z",
        market_phase="PREGAME",
        transport="anonymous_public_get_only_explicit_url",
        source_payload_sha256="a" * 64,
        markets={
            "moneyline": {
                "market_id": "dk-event-1-ml",
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


def _dk_collection(*, collected_at: datetime = NOW) -> dict:
    return {
        "collected_at_utc": _iso(collected_at),
        "snapshots": [_dk_snapshot()],
        "rejected_snapshot_count": 0,
    }


def _collect(**overrides):
    kwargs = {
        "now_utc": NOW,
        "include_fanduel_game_odds": True,
        "include_fanduel_player_props": False,
        "include_draftkings": False,
        "fanduel_game_collector": lambda **_: _fd_game_collection(),
        "fanduel_prop_collector": lambda **_: _fd_prop_collection(),
        "draftkings_collector": lambda **_: _dk_collection(),
        "sleeper": lambda _: None,
    }
    kwargs.update(overrides)
    return collect_reliable_mlb_market_feed(**kwargs)


def _provider(result: dict, key: str) -> dict:
    return next(row for row in result["provider_reliability"] if row["provider_key"] == key)


def _cooldown_state(provider: str, until: datetime) -> dict:
    return {
        "schema_version": 1,
        "providers": {
            provider: {
                "cooldown_until_utc": _iso(until),
                "cooldown_reason": "test",
                "last_failure_kind": "test",
                "last_failure_at_utc": _iso(NOW - timedelta(seconds=1)),
                "last_success_at_utc": None,
            }
        },
    }


def test_manifest_freezes_step19d_boundary():
    manifest = reliability_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["step19d_base_main_sha"] == STEP19D_BASE_MAIN_SHA
    assert manifest["reliability_status"] == RELIABILITY_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["bounded_retry_enabled"] is True
    assert manifest["provider_cooldown_enabled"] is True
    assert manifest["rate_limit_cooldown_enabled"] is True
    assert manifest["stale_snapshot_detection_enabled"] is True
    assert manifest["retry_non_retryable_configuration_errors"] is False
    assert manifest["fallback_price_fabrication_allowed"] is False
    assert manifest["reliability_state_persisted_by_step19d"] is False
    assert manifest["production_runtime_wiring_added_by_step19d"] is False
    assert manifest["production_database_writes_enabled"] is False
    assert manifest["actionable_output_enabled"] is False
    assert manifest["wagering_enabled"] is False


def test_healthy_fanduel_read_passes_through_step19b():
    result = _collect()
    assert result["collection_status"] == "ok"
    assert result["market_feed"]["game_market_snapshot_count"] == 1
    assert result["market_feed"]["game_market_snapshots"][0]["provider_key"] == "fanduel"
    assert _provider(result, "fanduel")["status"] == "healthy"
    assert _provider(result, "fanduel")["network_attempt_count"] == 1
    assert result["retry_count"] == 0


def test_transient_timeout_retries_once_and_recovers():
    calls = {"count": 0}
    delays: list[float] = []

    def flaky(**_):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("temporary timeout")
        return _fd_game_collection()

    result = _collect(
        fanduel_game_collector=flaky,
        sleeper=delays.append,
        max_attempts=2,
    )
    assert calls["count"] == 2
    assert delays == [0.25]
    assert result["collection_status"] == "recovered"
    assert result["retry_count"] == 1
    assert result["market_feed"]["live_market_data_present"] is True
    assert result["reliability_state"]["providers"]["fanduel"]["cooldown_until_utc"] is None


def test_http_503_is_retryable():
    calls = {"count": 0}

    def flaky(**_):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("GET returned HTTP 503")
        return _fd_game_collection()

    result = _collect(fanduel_game_collector=flaky)
    assert calls["count"] == 2
    assert result["collection_status"] == "recovered"
    first = result["attempt_telemetry"][0]
    assert first["failure_kind"] == "transient_upstream"
    assert first["retryable"] is True


def test_http_404_is_not_retried_or_cooled_down():
    calls = {"count": 0}

    def rejected(**_):
        calls["count"] += 1
        raise RuntimeError("GET returned HTTP 404")

    result = _collect(fanduel_game_collector=rejected, max_attempts=3)
    assert calls["count"] == 1
    assert result["collection_status"] == "unavailable"
    assert result["retry_count"] == 0
    assert result["cooldown_enforced"] is False
    assert _provider(result, "fanduel")["failure_kinds"] == ["provider_rejected"]


def test_rate_limit_enters_cooldown_without_immediate_retry():
    calls = {"count": 0}
    delays: list[float] = []

    def limited(**_):
        calls["count"] += 1
        raise RuntimeError("HTTP Error 429: Too Many Requests")

    result = _collect(
        fanduel_game_collector=limited,
        max_attempts=3,
        sleeper=delays.append,
        cooldown_seconds=90,
    )
    assert calls["count"] == 1
    assert delays == []
    assert result["collection_status"] == "cooldown"
    assert result["cooldown_enforced"] is True
    assert _provider(result, "fanduel")["failure_kinds"] == ["rate_limited"]
    assert result["reliability_state"]["providers"]["fanduel"]["cooldown_reason"] == "rate_limited"


def test_transient_retries_exhausted_enters_cooldown():
    calls = {"count": 0}
    delays: list[float] = []

    def down(**_):
        calls["count"] += 1
        raise TimeoutError("still down")

    result = _collect(
        fanduel_game_collector=down,
        max_attempts=3,
        sleeper=delays.append,
    )
    assert calls["count"] == 3
    assert delays == [0.25, 0.5]
    assert result["collection_status"] == "cooldown"
    assert result["retry_count"] == 2
    state = result["reliability_state"]["providers"]["fanduel"]
    assert state["cooldown_reason"] == "transient_retries_exhausted"


def test_exponential_backoff_is_capped():
    calls = {"count": 0}
    delays: list[float] = []

    def flaky(**_):
        calls["count"] += 1
        if calls["count"] < 4:
            raise TimeoutError("temporary")
        return _fd_game_collection()

    result = _collect(
        fanduel_game_collector=flaky,
        max_attempts=4,
        base_backoff_seconds=0.75,
        max_backoff_seconds=1.0,
        sleeper=delays.append,
    )
    assert result["collection_status"] == "recovered"
    assert delays == [0.75, 1.0, 1.0]


def test_stale_provider_snapshot_fails_closed_and_enters_cooldown():
    stale = NOW - timedelta(seconds=121)
    result = _collect(
        fanduel_game_collector=lambda **_: _fd_game_collection(collected_at=stale),
        max_snapshot_age_seconds=120,
    )
    assert result["market_feed"]["live_market_data_present"] is False
    assert result["collection_status"] == "cooldown"
    assert _provider(result, "fanduel")["failure_kinds"] == ["stale_data"]
    assert result["retry_count"] == 0


def test_future_provider_snapshot_fails_closed_without_retry():
    future = NOW + timedelta(seconds=6)
    result = _collect(
        fanduel_game_collector=lambda **_: _fd_game_collection(collected_at=future),
        clock_skew_tolerance_seconds=5,
    )
    assert result["collection_status"] == "unavailable"
    assert _provider(result, "fanduel")["failure_kinds"] == ["future_timestamp"]
    assert result["retry_count"] == 0


def test_small_future_clock_skew_cannot_bypass_step19b_timestamp_guard():
    future = NOW + timedelta(seconds=4)
    result = _collect(
        fanduel_game_collector=lambda **_: _fd_game_collection(collected_at=future),
        clock_skew_tolerance_seconds=5,
    )
    assert result["collection_status"] == "empty"
    assert _provider(result, "fanduel")["status"] == "healthy"
    assert result["market_feed"]["game_market_snapshot_count"] == 0
    assert result["market_feed"]["rejected_record_count"] == 1


def test_missing_provider_timestamp_fails_closed():
    raw = _fd_game_collection()
    raw.pop("collected_at_utc")
    result = _collect(fanduel_game_collector=lambda **_: raw)
    assert result["collection_status"] == "unavailable"
    assert _provider(result, "fanduel")["failure_kinds"] == ["missing_timestamp"]


def test_non_mapping_provider_snapshot_fails_closed_without_retry():
    calls = {"count": 0}

    def malformed(**_):
        calls["count"] += 1
        return []

    result = _collect(fanduel_game_collector=malformed, max_attempts=3)
    assert calls["count"] == 1
    assert result["collection_status"] == "unavailable"
    assert _provider(result, "fanduel")["failure_kinds"] == ["malformed_snapshot"]


def test_active_provider_cooldown_skips_network_read():
    calls = {"count": 0}

    def should_not_run(**_):
        calls["count"] += 1
        return _fd_game_collection()

    result = _collect(
        reliability_state=_cooldown_state("fanduel", NOW + timedelta(seconds=30)),
        fanduel_game_collector=should_not_run,
    )
    assert calls["count"] == 0
    assert result["collection_status"] == "cooldown"
    assert result["market_feed"]["enabled_surface_count"] == 0
    assert _provider(result, "fanduel")["network_attempt_count"] == 0


def test_expired_cooldown_allows_provider_read_and_clears_failure():
    result = _collect(
        reliability_state=_cooldown_state("fanduel", NOW - timedelta(seconds=1)),
    )
    assert result["collection_status"] == "ok"
    state = result["reliability_state"]["providers"]["fanduel"]
    assert state["cooldown_until_utc"] is None
    assert state["last_failure_kind"] is None


def test_fanduel_cooldown_falls_back_to_draftkings():
    result = _collect(
        reliability_state=_cooldown_state("fanduel", NOW + timedelta(seconds=30)),
        include_draftkings=True,
        draftkings_collector=lambda **_: _dk_collection(),
    )
    assert result["collection_status"] == "fallback"
    assert result["fallback_used"] is True
    assert result["market_feed"]["providers_with_data"] == ["draftkings"]
    assert _provider(result, "fanduel")["status"] == "cooldown"
    assert _provider(result, "draftkings")["status"] == "healthy"


def test_draftkings_not_ready_does_not_poison_fanduel_fallback():
    calls = {"count": 0}

    def not_ready(**_):
        calls["count"] += 1
        raise MLBDraftKingsProviderNotReadyError("not configured")

    result = _collect(
        include_draftkings=True,
        draftkings_collector=not_ready,
    )
    assert calls["count"] == 1
    assert result["collection_status"] == "fallback"
    assert result["market_feed"]["providers_with_data"] == ["fanduel"]
    assert _provider(result, "draftkings")["status"] == "not_ready"
    assert _provider(result, "draftkings")["retry_count"] == 0


def test_exhausted_fanduel_transport_failure_falls_back_to_draftkings():
    def down(**_):
        raise TimeoutError("fanduel unavailable")

    result = _collect(
        fanduel_game_collector=down,
        include_draftkings=True,
        draftkings_collector=lambda **_: _dk_collection(),
        max_attempts=2,
    )
    assert result["collection_status"] == "fallback"
    assert result["market_feed"]["providers_with_data"] == ["draftkings"]
    assert _provider(result, "fanduel")["status"] == "cooldown"
    assert _provider(result, "draftkings")["status"] == "healthy"


def test_mid_collection_fanduel_rate_limit_suppresses_second_fanduel_surface():
    prop_calls = {"count": 0}

    def limited(**_):
        raise RuntimeError("HTTP 429")

    def prop(**_):
        prop_calls["count"] += 1
        return _fd_prop_collection()

    result = _collect(
        fanduel_game_collector=limited,
        include_fanduel_player_props=True,
        fanduel_prop_collector=prop,
    )
    assert prop_calls["count"] == 0
    assert result["collection_status"] == "cooldown"
    terminal = {
        row["surface"]: row
        for row in result["attempt_telemetry"]
        if row["provider_key"] == "fanduel"
    }
    assert terminal["fanduel_player_props"]["outcome"] == "cooldown_skip"


def test_one_fanduel_surface_can_degrade_without_erasing_valid_data():
    def broken_prop(**_):
        raise RuntimeError("malformed provider contract")

    result = _collect(
        include_fanduel_player_props=True,
        fanduel_prop_collector=broken_prop,
    )
    assert result["collection_status"] == "fallback"
    assert result["market_feed"]["game_market_snapshot_count"] == 1
    assert result["market_feed"]["player_prop_count"] == 0
    assert _provider(result, "fanduel")["status"] == "degraded"
    assert result["reliability_state"]["providers"]["fanduel"]["cooldown_until_utc"] is None


def test_both_fanduel_surfaces_healthy():
    result = _collect(include_fanduel_player_props=True)
    assert result["collection_status"] == "ok"
    assert result["market_feed"]["game_market_snapshot_count"] == 1
    assert result["market_feed"]["player_prop_count"] == 1
    assert _provider(result, "fanduel")["status"] == "healthy"


def test_stale_player_prop_snapshot_is_rejected_before_step19b_accepts_props():
    stale = NOW - timedelta(minutes=3)
    result = _collect(
        include_fanduel_game_odds=False,
        include_fanduel_player_props=True,
        fanduel_prop_collector=lambda **_: _fd_prop_collection(collected_at=stale),
    )
    assert result["market_feed"]["player_prop_count"] == 0
    assert result["collection_status"] == "cooldown"
    assert _provider(result, "fanduel")["failure_kinds"] == ["stale_data"]


def test_empty_successful_provider_read_is_empty_not_unavailable():
    result = _collect(
        fanduel_game_collector=lambda **_: _fd_game_collection(games=[]),
    )
    assert result["collection_status"] == "empty"
    assert _provider(result, "fanduel")["status"] == "healthy"
    assert result["market_feed"]["live_market_data_present"] is False


def test_no_requested_surfaces_performs_no_provider_reads():
    result = _collect(
        include_fanduel_game_odds=False,
        include_fanduel_player_props=False,
        include_draftkings=False,
    )
    assert result["collection_status"] == "empty"
    assert result["provider_reliability"] == []
    assert result["attempt_telemetry"] == []
    assert result["market_feed"]["enabled_surface_count"] == 0


def test_output_preserves_read_only_and_no_fabrication_invariants():
    result = _collect()
    assert result["network_reads_only"] is True
    assert result["http_methods"] == ["GET"]
    assert result["price_fabrication_used"] is False
    assert result["synthetic_game_id_used"] is False
    assert result["synthetic_player_id_used"] is False
    assert result["fuzzy_matching_used"] is False
    assert result["reliability_state_persisted_by_step19d"] is False
    assert result["production_runtime_wiring"] is False
    assert result["production_database_writes"] is False
    assert result["model_probability_mutation"] is False
    assert result["projection_mutation"] is False
    assert result["actionable_output"] is False
    assert result["wagering"] is False
    assert result["market_feed"]["price_fabrication_used"] is False


def test_reliability_state_is_copied_not_mutated_in_place():
    state = _cooldown_state("fanduel", NOW - timedelta(seconds=1))
    original_until = state["providers"]["fanduel"]["cooldown_until_utc"]
    result = _collect(reliability_state=state)
    assert state["providers"]["fanduel"]["cooldown_until_utc"] == original_until
    assert result["reliability_state"]["providers"]["fanduel"]["cooldown_until_utc"] is None


@pytest.mark.parametrize(
    ("overrides", "category"),
    [
        ({"max_attempts": 0}, "invalid_policy"),
        ({"max_attempts": 6}, "invalid_policy"),
        ({"max_attempts": 1.5}, "invalid_policy"),
        ({"base_backoff_seconds": -0.1}, "invalid_policy"),
        ({"base_backoff_seconds": 2.0, "max_backoff_seconds": 1.0}, "invalid_policy"),
        ({"cooldown_seconds": 0}, "invalid_policy"),
        ({"max_snapshot_age_seconds": 0}, "invalid_policy"),
        ({"clock_skew_tolerance_seconds": -1}, "invalid_policy"),
        ({"sleeper": None}, "invalid_policy"),
        ({"include_fanduel_game_odds": 1}, "invalid_policy"),
    ],
)
def test_invalid_policy_fails_closed(overrides, category):
    with pytest.raises(MLBProviderReliabilityError) as exc:
        _collect(**overrides)
    assert exc.value.category == category


def test_naive_now_fails_closed():
    with pytest.raises(MLBProviderReliabilityError) as exc:
        _collect(now_utc=datetime(2026, 9, 2, 4, 15))
    assert exc.value.category == "malformed_timestamp"


def test_unknown_provider_in_state_fails_closed():
    with pytest.raises(MLBProviderReliabilityError) as exc:
        _collect(
            reliability_state={
                "schema_version": 1,
                "providers": {"otherbook": {}},
            }
        )
    assert exc.value.category == "invalid_state"


def test_bad_state_timestamp_fails_closed():
    with pytest.raises(MLBProviderReliabilityError) as exc:
        _collect(
            reliability_state={
                "schema_version": 1,
                "providers": {
                    "fanduel": {"cooldown_until_utc": "not-a-time"},
                },
            }
        )
    assert exc.value.category == "malformed_timestamp"


def test_default_retry_count_is_bounded():
    assert DEFAULT_MAX_ATTEMPTS == 2
    calls = {"count": 0}

    def down(**_):
        calls["count"] += 1
        raise TimeoutError("down")

    _collect(fanduel_game_collector=down)
    assert calls["count"] == DEFAULT_MAX_ATTEMPTS
