from __future__ import annotations

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19f_draftkings_identity as step19f
from sports_api import wnba_step19g_hosted_provider_trace as step19g


def _sample_result() -> dict:
    return {
        "status": "half_open_failed",
        "health": "blocked",
        "slate_date": "2026-08-29",
        "provider_discovery": {
            "draftkings": {
                "provider": "DraftKings",
                "attempt_limit": 1,
                "attempts_executed": 1,
                "retryable_failures": 0,
                "record_count": 42,
                "bridge_content_sha256": "a" * 64,
                "errors": [],
                "records": [{"secret_market_payload": "must_not_escape"}],
            },
            "fanduel": {
                "provider": "FanDuel",
                "attempt_limit": 1,
                "attempts_executed": 1,
                "retryable_failures": 1,
                "record_count": 0,
                "bridge_content_sha256": None,
                "errors": [
                    {
                        "attempt": 1,
                        "error_type": "WNBAStep11FanDuelProviderUpstreamError",
                        "error_message": "Step 11C GET returned HTTP 403.",
                    }
                ],
            },
            "transient_provider_short_circuit": True,
        },
        "step12a_result": {
            "step11e_tick": {"execution": {"cycle_outcome": "provider_transient_not_ready"}}
        },
    }


def test_trace_is_sanitized_and_preserves_provider_failure_identity():
    step19g._capture_result(_sample_result())
    trace = step19g.get_step19g_hosted_provider_trace()
    latest = trace["latest"]
    assert latest["cycle_outcome"] == "provider_transient_not_ready"
    assert latest["draftkings"]["record_count"] == 42
    assert latest["fanduel"]["record_count"] == 0
    assert latest["fanduel"]["errors"][0]["error_type"] == "WNBAStep11FanDuelProviderUpstreamError"
    assert "403" in latest["fanduel"]["errors"][0]["error_message"]
    assert "records" not in latest["draftkings"]
    assert "secret_market_payload" not in repr(trace)
    assert latest["guardrails"]["market_records_exposed"] is False
    assert latest["guardrails"]["secrets_exposed"] is False


def test_install_keeps_step19f_fanduel_compatibility_active():
    status = step19g.install_step19g_hosted_provider_trace()
    assert status["installed"] is True
    assert step12b.run_step12b_live_runtime_job is step19g.run_step12b_with_hosted_trace
    assert fanduel._relevant_tab_ids is step19f.fanduel_relevant_tab_ids_step19f
    assert status["compatibility"]["fanduel_tab_slug_patch_active"] is True
    assert status["readiness_relaxed"] is False
    assert status["projection_logic_modified"] is False
    assert status["controller_state_modified"] is False


def test_wrapper_returns_original_result_unchanged():
    original = step19g._ORIGINAL_RUN_STEP12B
    expected = _sample_result()

    def fake_runner(*args, **kwargs):
        return expected

    try:
        step19g._ORIGINAL_RUN_STEP12B = fake_runner
        actual = step19g.run_step12b_with_hosted_trace({"ignored": True})
    finally:
        step19g._ORIGINAL_RUN_STEP12B = original

    assert actual is expected
    assert actual == expected


def test_wrapper_re_raises_original_exception_after_sanitized_capture():
    original = step19g._ORIGINAL_RUN_STEP12B

    def fake_runner(*args, **kwargs):
        raise RuntimeError("provider exploded safely")

    try:
        step19g._ORIGINAL_RUN_STEP12B = fake_runner
        try:
            step19g.run_step12b_with_hosted_trace({})
        except RuntimeError as exc:
            assert str(exc) == "provider exploded safely"
        else:
            raise AssertionError("exception was not re-raised")
    finally:
        step19g._ORIGINAL_RUN_STEP12B = original

    trace = step19g.get_step19g_hosted_provider_trace()
    assert trace["latest"]["exception"]["error_type"] == "RuntimeError"
    assert trace["latest"]["guardrails"]["read_only_trace"] is True
