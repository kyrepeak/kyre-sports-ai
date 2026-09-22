from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from sports_api import wnba_step19a_consumer_verifier as verifier

AT = datetime(2026, 8, 29, 7, 0, 10, tzinfo=timezone.utc)


def _semantics() -> dict:
    return {
        "read_only_get": True,
        "in_memory_snapshot_only": True,
        "database_connection_opened": False,
        "database_read_performed": False,
        "database_write_performed": False,
        "scheduler_started": False,
        "scheduler_cycle_triggered": False,
        "sportsbook_network_called": False,
        "projection_run": False,
        "monte_carlo_run": False,
        "wager_action_performed": False,
        "database_secret_exposed": False,
        "new_render_service_created": False,
    }


def _card(*, rank: int = 1, books: int = 2) -> dict:
    return {
        "display_rank": rank,
        "frozen_rank": rank,
        "ranking": "pure_probability",
        "candidate_id": f"candidate-{rank}",
        "qualification": "qualified",
        "player": {
            "player_id": 1000 + rank,
            "player_name": f"Player {rank}",
            "team_key": "PHX",
            "opponent_team_key": "TOR",
            "game_id": "1022600291",
        },
        "prop": {
            "stat": "points",
            "stat_label": "Points",
            "side": "over",
            "line": 20.5,
            "pick": "OVER 20.5",
        },
        "market": {
            "sportsbook": "DraftKings" if rank == 1 else "FanDuel",
            "american_odds": -110,
            "decimal_odds": 1.90909091,
            "captured_at_utc": "2026-08-29T07:00:00+00:00",
            "age_seconds_at_evaluation": 10.0,
        },
        "model": {
            "resolved_fair_probability": 0.63,
            "resolved_fair_percentage": 63.0,
            "raw_win_probability": 0.62,
            "raw_win_percentage": 62.0,
            "push_probability": 0.01,
            "push_percentage": 1.0,
            "simulations": 5_000_000,
            "batch_size": 250_000,
            "converged": True,
        },
        "consensus": {
            "no_vig_probability": 0.51,
            "no_vig_percentage": 51.0,
            "edge_probability": 0.12,
            "edge_percentage_points": 12.0,
            "book_count_at_exact_line": books,
            "market_probability_range_percentage_points": 1.2,
        },
        "value": {"ev_per_unit": 0.2027, "ev_roi_percentage": 20.27},
        "qualification_margin": {},
        "lineage": {},
    }


def _payload() -> dict:
    cards = [_card(rank=1), _card(rank=2)]
    return {
        "data_type": verifier.EXPECTED_DATA_TYPE,
        "schema_version": verifier.EXPECTED_SCHEMA_VERSION,
        "consumer_version": "certified-step18a",
        "source": "Kyre Sports API",
        "generated_at_utc": AT.isoformat(),
        "enabled": True,
        "available": True,
        "reason": "board_ready",
        "slate_date": "2026-08-29",
        "health": "healthy",
        "snapshot": {
            "captured_at_utc": "2026-08-29T07:00:00+00:00",
            "source_generated_at_utc": "2026-08-29T06:59:59+00:00",
            "age_seconds": 10.0,
            "stale_after_seconds": 180,
            "stale": False,
            "snapshot_content_sha256": "a" * 64,
        },
        "board": {
            "available": True,
            "ranking_method": "frozen_probability",
            "requested_top_card_count": 5,
            "qualified_prop_count": 2,
            "top_card_count": 2,
            "full_requested_board_available": False,
            "top_n_forced": False,
            "primary_top_cards": cards,
            "value_ranking": [],
            "reason": None,
        },
        "runtime": {
            "status": "healthy",
            "health": "healthy",
            "cycle_executed": True,
            "cycle_outcome": "shadow_board_ready",
            "circuit_state": "closed",
            "next_refresh_due_at_utc": "2026-08-29T07:01:00+00:00",
        },
        "lineage": {
            "source_step13a_scheduler_content_sha256": "b" * 64,
            "source_step13c_reliability_content_sha256": "c" * 64,
        },
        "semantics": _semantics(),
    }


def _reject(payload: dict, text: str | None = None) -> None:
    with pytest.raises(verifier.WNBAStep19AConsumerVerificationError) as caught:
        verifier.verify_consumer_latest(
            payload,
            evaluated_at=AT,
            expected_slate_date="2026-08-29",
        )
    if text:
        assert text.casefold() in str(caught.value).casefold()


def test_real_step18a_shape_passes_only_when_genuinely_ready() -> None:
    result = verifier.verify_consumer_latest(
        _payload(), evaluated_at=AT, expected_slate_date="2026-08-29"
    )
    assert result["ready"] is True
    assert result["health"] == "healthy"
    assert result["top_card_count"] == 2
    assert result["minimum_exact_line_book_count"] == 2
    assert result["production_or_write_action_performed"] is False


def test_http_200_style_payload_with_unavailable_board_fails_closed() -> None:
    payload = _payload()
    payload["available"] = False
    payload["reason"] = "not_executed"
    _reject(payload, "unavailable")


def test_stale_flag_fails_closed() -> None:
    payload = _payload()
    payload["snapshot"]["stale"] = True
    _reject(payload, "stale")


def test_effectively_stale_age_fails_even_if_stale_flag_is_false() -> None:
    payload = _payload()
    payload["snapshot"]["age_seconds"] = 181.1
    _reject(payload, "effectively stale")


@pytest.mark.parametrize("health", ["degraded", "blocked", "market_not_ready", "waiting"])
def test_nonhealthy_top_level_health_is_rejected(health: str) -> None:
    payload = _payload()
    payload["health"] = health
    _reject(payload, "not healthy")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "transient_failure"),
        ("health", "degraded"),
        ("cycle_outcome", "provider_transient_not_ready"),
        ("circuit_state", "open"),
    ],
)
def test_runtime_readiness_disagreement_is_rejected(field: str, value: str) -> None:
    payload = _payload()
    payload["runtime"][field] = value
    _reject(payload)


def test_one_book_exact_line_card_is_rejected() -> None:
    payload = _payload()
    payload["board"]["primary_top_cards"][0]["consensus"]["book_count_at_exact_line"] = 1
    _reject(payload, "two-sportsbook")


def test_nonconverged_or_wrong_simulation_count_is_rejected() -> None:
    payload = _payload()
    payload["board"]["primary_top_cards"][0]["model"]["converged"] = False
    _reject(payload, "converge")

    payload = _payload()
    payload["board"]["primary_top_cards"][0]["model"]["simulations"] = 10_000
    _reject(payload, "5m")


def test_forced_padded_top_n_is_rejected() -> None:
    payload = _payload()
    payload["board"]["top_n_forced"] = True
    _reject(payload, "forced")


def test_board_count_tamper_is_rejected() -> None:
    payload = _payload()
    payload["board"]["top_card_count"] = 5
    _reject(payload, "count identity")


def test_wrong_schema_and_missing_snapshot_fail_closed() -> None:
    payload = _payload()
    payload["schema_version"] = "wrong"
    _reject(payload, "schema")

    payload = _payload()
    payload.pop("snapshot")
    _reject(payload, "snapshot")


def test_wrong_slate_is_rejected() -> None:
    payload = _payload()
    payload["slate_date"] = "2026-08-30"
    _reject(payload, "slate mismatch")


def test_unsafe_read_semantics_are_rejected() -> None:
    payload = _payload()
    payload["semantics"]["sportsbook_network_called"] = True
    _reject(payload, "semantic drift")


def test_future_capture_time_is_rejected() -> None:
    payload = _payload()
    payload["snapshot"]["captured_at_utc"] = "2026-08-29T07:10:00+00:00"
    _reject(payload, "future")


def test_original_step18a_runtime_shape_with_only_next_due_is_accepted() -> None:
    payload = _payload()
    payload["runtime"] = {
        "next_refresh_due_at_utc": "2026-08-29T07:01:00+00:00"
    }
    result = verifier.verify_consumer_latest(
        payload, evaluated_at=AT, expected_slate_date="2026-08-29"
    )
    assert result["ready"] is True
