from __future__ import annotations

import pytest

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


def test_trace_wrapper_reraises_same_exception_type_and_message():
    class Boom(RuntimeError):
        pass
    def upstream(*args, **kwargs):
        raise Boom("unchanged")
    wrapped = trace._make_wrapper("player_opportunity_context", upstream)
    with pytest.raises(Boom, match="unchanged"):
        wrapped(123, 2026)


def test_installer_is_diagnostic_only_and_all_bindings_are_active():
    status = trace.install_step20b_rollover_stage_trace()
    assert status["installed"] is True
    assert status["all_stage_wrappers_active"] is True
    assert all(status["active_bindings"].values())
    guards = status["guardrails"]
    assert guards["diagnostic_only"] is True
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
