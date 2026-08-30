from __future__ import annotations

from sports_api import wnba_step12b_live_runtime_assembly as s12b
from sports_api import wnba_step20b_render_inflight_trace as trace


def test_install_patches_only_private_orchestration_seams():
    s12b._fetch_provider_bridge = trace._ORIGINAL_FETCH_PROVIDER_BRIDGE
    s12b._exact_multibook_targets = trace._ORIGINAL_EXACT_MULTIBOOK_TARGETS
    s12b._build_frozen_step8_distribution = trace._ORIGINAL_BUILD_FROZEN_STEP8_DISTRIBUTION
    run_before = s12b.run_step12b_live_runtime_job

    status = trace.install_step20b_render_inflight_trace()

    assert s12b.run_step12b_live_runtime_job is run_before
    assert all(status["private_seams_active"].values())
    guards = status["guardrails"]
    for key in (
        "official_data_provider_seams_modified",
        "sportsbook_transport_modified",
        "player_identity_modified",
        "exact_line_matching_modified",
        "different_lines_blended",
        "player_coverage_modified",
        "step8_call_order_modified",
        "projection_math_modified",
        "monte_carlo_simulation_count_modified",
        "monte_carlo_batch_size_modified",
        "readiness_relaxed",
        "controller_state_modified",
        "durable_lease_policy_modified",
        "persistence_modified",
        "wagering_enabled",
    ):
        assert guards[key] is False


def test_step8_trace_preserves_exact_phase_order_and_certified_mc(monkeypatch):
    calls = []
    handoff = {"handoff": True}
    baseline = {"baseline": True}
    adjusted = {"adjusted": True}
    distribution = {"distribution": True}

    def fake_handoff(player_id, game_id, *, env=None):
        calls.append(("8a", player_id, game_id, env))
        return handoff

    def fake_baseline(value):
        calls.append(("8b", value))
        return baseline

    def fake_adjusted(h, b):
        calls.append(("8c", h, b))
        return adjusted

    def fake_mc(a, b, *, simulations, batch_size, env=None):
        calls.append(("8d", a, b, simulations, batch_size, env))
        return distribution

    monkeypatch.setattr(s12b.step8a, "get_player_game_step8_projection_handoff", fake_handoff)
    monkeypatch.setattr(s12b.step8b, "build_step8_official_box_baseline", fake_baseline)
    monkeypatch.setattr(s12b.step8c, "build_step8_context_adjusted_projection", fake_adjusted)
    monkeypatch.setattr(s12b.step8d, "simulate_step8_joint_distribution", fake_mc)

    result = trace.build_frozen_step8_distribution_step20b_trace(
        game_id="1022600001", player_id=123, env={"SAFE": "1"}
    )

    assert result is distribution
    assert [row[0] for row in calls] == ["8a", "8b", "8c", "8d"]
    assert calls[-1][3] == 5_000_000
    assert calls[-1][4] == 250_000
    assert s12b.CERTIFIED_SIMULATIONS == 5_000_000
    assert s12b.CERTIFIED_BATCH_SIZE == 250_000


def test_exact_target_trace_returns_original_value_unchanged(monkeypatch):
    expected = ([('1022600001', 123)], [{"group": True}])

    def fake_original(dk, fd):
        assert dk == [{"dk": True}]
        assert fd == [{"fd": True}]
        return expected

    monkeypatch.setattr(trace, "_ORIGINAL_EXACT_MULTIBOOK_TARGETS", fake_original)
    result = trace.exact_multibook_targets_step20b_trace(
        [{"dk": True}], [{"fd": True}]
    )
    assert result is expected
    status = trace.installation_status()["trace"]
    assert status["target_total"] == 1
    assert status["exact_group_count"] == 1


def test_provider_trace_returns_original_value_and_records_count(monkeypatch):
    expected = ({"bridge": True}, {"record_count": 17})

    def fake_original(*args, **kwargs):
        assert kwargs["provider"] == "DraftKings"
        return expected

    monkeypatch.setattr(trace, "_ORIGINAL_FETCH_PROVIDER_BRIDGE", fake_original)
    result = trace.fetch_provider_bridge_step20b_trace(provider="DraftKings")
    assert result is expected
    status = trace.installation_status()["trace"]
    assert status["provider_timings"]["DraftKings"]["record_count"] == 17


def test_step8_exception_is_re_raised_and_recorded(monkeypatch):
    class MarkerError(RuntimeError):
        pass

    def fail(*args, **kwargs):
        raise MarkerError("marker")

    monkeypatch.setattr(s12b.step8a, "get_player_game_step8_projection_handoff", fail)
    try:
        trace.build_frozen_step8_distribution_step20b_trace(
            game_id="1022600001", player_id=123, env={}
        )
    except MarkerError as exc:
        assert str(exc) == "marker"
    else:
        raise AssertionError("expected MarkerError")

    status = trace.installation_status()["trace"]
    assert status["last_error_type"] == "MarkerError"
    assert status["target_raised_count"] >= 1
