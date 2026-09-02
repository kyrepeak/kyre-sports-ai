from __future__ import annotations

import pytest

from sports_api import wnba_projection_input_snapshot as projection_snapshot
from sports_api import wnba_step7g_first_party_integration as step7g
from sports_api import wnba_step20b_rollover_stage_trace as trace


def test_trace_wrapper_returns_upstream_value_unchanged():
    seen = []

    def upstream(*args, **kwargs):
        seen.append((args, kwargs))
        return {"ok": True, "value": [1, 2, 3]}

    wrapped = trace._make_wrapper("matchup_source_status", upstream)
    result = wrapped(2026, mode="x")
    assert result == {"ok": True, "value": [1, 2, 3]}
    assert seen == [((2026,), {"mode": "x"})]


def test_trace_wrapper_reraises_same_exception_and_records_safe_error_details():
    class Boom(RuntimeError):
        pass

    def upstream(*args, **kwargs):
        raise Boom("unchanged")

    stage = "step20b_test_boom"
    wrapped = trace._make_wrapper(stage, upstream)
    with pytest.raises(Boom, match="unchanged"):
        wrapped(123, 2026)

    event = next(
        row
        for row in reversed(trace.installation_status()["recent_completed"])
        if row["stage"] == stage
    )
    assert event["status"] == "raised"
    assert event["error_type"] == "Boom"
    assert event["error_message"] == "unchanged"
    assert "Boom" in event["error_repr"]
    assert event["traceback_tail"]
    assert all({"file", "line", "function"} <= set(frame) for frame in event["traceback_tail"])


def test_optional_dispatch_uses_component_specific_stage_name():
    def upstream(*args, **kwargs):
        return {"ok": True}

    wrapped = trace._make_wrapper(trace._OPTIONAL_DISPATCH_STAGE, upstream)
    assert wrapped("player_recent_shot_chart", object()) == {"ok": True}

    event = next(
        row
        for row in reversed(trace.installation_status()["recent_completed"])
        if row["stage"] == "step4w_optional_player_recent_shot_chart"
    )
    assert event["status"] == "returned"


def test_installer_is_identity_safe_and_all_bindings_are_active():
    protected_before = {
        attr: getattr(projection_snapshot, attr)
        for attr in trace._STEP7G_PROTECTED_STEP4W_ATTRS
    }

    status = trace.install_step20b_rollover_stage_trace()

    assert status["installed"] is True
    assert status["all_stage_wrappers_active"] is True
    assert all(status["active_bindings"].values())
    assert status["protected_step7g_step4w_bindings_untouched"] is True
    assert status["protected_step7g_step4w_bindings_wrapped"] == []
    assert {
        attr: getattr(projection_snapshot, attr)
        for attr in trace._STEP7G_PROTECTED_STEP4W_ATTRS
    } == protected_before

    # Re-run the exact Step7G identity checks that v3 violated. These calls do
    # not mutate the seams; they only prove the current object identity is
    # acceptable to Step7G.
    checks = (
        (
            "Step 4W player-shot provider",
            projection_snapshot.get_player_shot_chart_dataset,
            step7g._ORIGINAL_PROJECTION_PLAYER_SHOT,
            step7g.get_first_party_player_shot_chart_dataset,
        ),
        (
            "Step 4W opponent-zone provider",
            projection_snapshot.get_opponent_defense_by_shot_zone_dataset,
            step7g._ORIGINAL_PROJECTION_OPPONENT_ZONE,
            step7g.get_first_party_opponent_defense_by_shot_zone_dataset,
        ),
        (
            "Step 4W player-advanced provider",
            projection_snapshot.get_player_advanced_stats_dataset,
            step7g._ORIGINAL_PROJECTION_PLAYER_ADVANCED,
            step7g.get_first_party_player_advanced_stats_dataset,
        ),
        (
            "Step 4W team-advanced provider",
            projection_snapshot.get_team_advanced_stats_dataset,
            step7g._ORIGINAL_PROJECTION_TEAM_ADVANCED,
            step7g.get_first_party_team_advanced_stats_dataset,
        ),
        (
            "Step 4W game-whistle provider",
            projection_snapshot.get_game_whistle_context,
            step7g._ORIGINAL_PROJECTION_GAME_WHISTLE,
            step7g.get_first_party_game_whistle_context,
        ),
    )
    for label, current, original, target in checks:
        assert step7g._guarded_replace(
            label=label,
            current=current,
            original=original,
            target=target,
        ) is target

    guards = status["guardrails"]
    assert guards["diagnostic_only"] is True
    assert guards["frozen_step7g_source_seams_patched"] is False
    for key in (
        "arguments_modified",
        "return_values_modified",
        "exceptions_reclassified",
        "execution_order_modified",
        "projection_math_modified",
        "monte_carlo_simulation_count_modified",
        "monte_carlo_batch_size_modified",
        "sportsbook_transport_modified",
        "readiness_relaxed",
        "persistence_modified",
        "wagering_enabled",
    ):
        assert guards[key] is False
