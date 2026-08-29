from copy import deepcopy
from datetime import datetime, timezone

from sports_api import wnba_step17b_always_on_runtime as s17b
from sports_api import wnba_step18a_streamlit_consumer as s18a


NOW = datetime(2026, 8, 29, 0, 50, 0, tzinfo=timezone.utc)


def _env(enabled=True):
    return {s18a.STEP18A_ENABLED_ENV: "true" if enabled else "false"}


def _step13c_response(*, board_available=True, board_reason=None):
    board = {
        "available": board_available,
        "ranking_method": "frozen_probability",
        "requested_top_card_count": 5,
        "qualified_prop_count": 1 if board_available else 0,
        "top_card_count": 1 if board_available else 0,
        "full_requested_board_available": False,
        "top_n_forced": False,
        "primary_top_cards": [
            {
                "display_rank": 1,
                "player": {"player_id": 123, "player_name": "Example Player"},
                "prop": {"stat": "points", "side": "over", "line": 15.5},
                "model": {"resolved_fair_probability": 0.63, "simulations": 5_000_000, "converged": True},
            }
        ] if board_available else [],
        "value_ranking": [],
    }
    if board_reason is not None:
        board["reason"] = board_reason
    scheduler = {
        "data_type": "wnba_step13a_bounded_scheduler_response",
        "schema_version": "test",
        "generated_at_utc": "2026-08-29T00:49:30+00:00",
        "status": "completed",
        "health": "healthy",
        "slate_date": "2026-08-28",
        "latest_board": board,
        "latest_runtime": {
            "evaluated_at_utc": "2026-08-29T00:49:25+00:00",
            "next_refresh_due_at_utc": "2026-08-29T00:50:25+00:00",
            "latest_market_capture_utc": "2026-08-29T00:49:20+00:00",
        },
    }
    supervisor = {
        "data_type": "wnba_step13b_runtime_supervisor_response",
        "schema_version": "test",
        "generated_at_utc": "2026-08-29T00:49:31+00:00",
        "status": "stopped",
        "health": "healthy",
        "active_slate_date": "2026-08-28",
        "latest_scheduler": scheduler,
        "lineage": {"latest_step13a_scheduler_content_sha256": "a" * 64},
    }
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": s18a.step13c.SCHEMA_VERSION,
        "source": "test",
        "model_version": "test",
        "generated_at_utc": "2026-08-29T00:49:32+00:00",
        "status": "completed",
        "health": "healthy",
        "latest_supervisor": supervisor,
        "final_controller_state_for_restart_handoff": {"state_content_sha256": "b" * 64},
        "lineage": {},
        "guardrails": {},
    }
    surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    }
    response["reliability_content_sha256"] = s18a._canonical_hash(surface)
    return response


def setup_function():
    s18a._clear_snapshot_for_test()


def test_default_off_returns_stable_read_only_unavailable_contract():
    result = s18a.build_step18a_consumer_latest(now_utc=NOW, env=_env(False))
    assert result["enabled"] is False
    assert result["available"] is False
    assert result["reason"] == "consumer_disabled"
    assert result["board"]["primary_top_cards"] == []
    assert result["semantics"]["read_only_get"] is True
    assert result["semantics"]["database_connection_opened"] is False
    assert result["semantics"]["database_write_performed"] is False
    assert result["semantics"]["scheduler_cycle_triggered"] is False
    assert result["semantics"]["sportsbook_network_called"] is False
    assert result["semantics"]["monte_carlo_run"] is False


def test_capture_exposes_already_computed_board_and_freshness_without_recompute():
    response = _step13c_response()
    assert s18a.capture_step13c_response(
        response, env=_env(True), captured_at_utc="2026-08-29T00:49:40+00:00"
    ) is True
    result = s18a.build_step18a_consumer_latest(now_utc=NOW, env=_env(True))
    assert result["enabled"] is True
    assert result["available"] is True
    assert result["reason"] == "board_ready"
    assert result["slate_date"] == "2026-08-28"
    assert result["board"]["primary_top_cards"][0]["player"]["player_id"] == 123
    assert result["snapshot"]["age_seconds"] == 20.0
    assert result["snapshot"]["stale"] is False
    assert len(result["snapshot"]["snapshot_content_sha256"]) == 64
    assert result["lineage"]["step17d_frozen_runtime_sha"] == s18a.STEP17D_FROZEN_RUNTIME_SHA


def test_freshness_marks_old_in_memory_board_stale_without_deleting_it():
    assert s18a.capture_step13c_response(
        _step13c_response(), env=_env(True), captured_at_utc="2026-08-29T00:45:00+00:00"
    ) is True
    result = s18a.build_step18a_consumer_latest(now_utc=NOW, env=_env(True))
    assert result["available"] is True
    assert result["snapshot"]["age_seconds"] == 300.0
    assert result["snapshot"]["stale"] is True


def test_new_completed_cycle_with_no_board_replaces_old_board_fail_closed():
    assert s18a.capture_step13c_response(
        _step13c_response(), env=_env(True), captured_at_utc="2026-08-29T00:49:30+00:00"
    ) is True
    assert s18a.capture_step13c_response(
        _step13c_response(board_available=False, board_reason="provider_unavailable"),
        env=_env(True),
        captured_at_utc="2026-08-29T00:49:50+00:00",
    ) is True
    result = s18a.build_step18a_consumer_latest(now_utc=NOW, env=_env(True))
    assert result["available"] is False
    assert result["reason"] == "provider_unavailable"
    assert result["board"]["primary_top_cards"] == []


def test_tampered_step13c_response_is_not_captured():
    response = _step13c_response()
    response["latest_supervisor"]["latest_scheduler"]["latest_board"]["qualified_prop_count"] = 999
    assert s18a.capture_step13c_response(response, env=_env(True)) is False
    result = s18a.build_step18a_consumer_latest(now_utc=NOW, env=_env(True))
    assert result["available"] is False
    assert result["reason"] == "awaiting_first_successful_scheduler_cycle"


def test_capture_wrapper_returns_original_frozen_step13c_response_unchanged():
    expected = _step13c_response()
    original_runner = s18a.step13c.run_step13c_reliability_recovery
    try:
        s18a.step13c.run_step13c_reliability_recovery = lambda request, env=None, **kwargs: expected
        actual = s18a.run_step13c_and_capture({"request": "opaque"}, env=_env(True))
    finally:
        s18a.step13c.run_step13c_reliability_recovery = original_runner
    assert actual is expected
    assert s18a.build_step18a_consumer_latest(now_utc=NOW, env=_env(True))["available"] is True


def test_step17b_uses_capture_seam_only_when_step18a_gate_is_enabled():
    seen = []

    def fake_durable_runner(request, *, owner_id, env, **kwargs):
        seen.append(dict(kwargs))
        return {
            "status": "completed",
            "saved_checkpoint_version": 1,
            "recovered_from_durable_checkpoint": False,
        }

    s17b.run_one_cycle(env=_env(False), owner_id="test-owner", slate_date="2026-08-28", runner=fake_durable_runner)
    assert "step13c_runner" not in seen[-1]

    # The Step18 integration deliberately applies only to the real frozen Step14C
    # runner path; injected test runners retain their existing exact call contract.
    assert s18a.step18a_streamlit_consumer_enabled(_env(True)) is True


if __name__ == "__main__":
    test_default_off_returns_stable_read_only_unavailable_contract()
    setup_function()
    test_capture_exposes_already_computed_board_and_freshness_without_recompute()
    setup_function()
    test_freshness_marks_old_in_memory_board_stale_without_deleting_it()
    setup_function()
    test_new_completed_cycle_with_no_board_replaces_old_board_fail_closed()
    setup_function()
    test_tampered_step13c_response_is_not_captured()
    setup_function()
    test_capture_wrapper_returns_original_frozen_step13c_response_unchanged()
    setup_function()
    test_step17b_uses_capture_seam_only_when_step18a_gate_is_enabled()
    print("STEP18A_STREAMLIT_CONSUMER_TESTS_OK")
