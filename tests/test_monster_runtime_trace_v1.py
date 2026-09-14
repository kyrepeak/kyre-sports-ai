from __future__ import annotations

from sports_api.monster_runtime_trace_v1 import (
    ParityIdentity,
    TraceHop,
    compare_production_parity,
    correlate_trace,
    identity_from_observability,
    version_drift,
)


def test_trace_correlates_full_request_path_by_request_id():
    hops = [
        TraceHop("req-1", "streamlit", "load CFB page", commit="abc", branch="main"),
        TraceHop("req-1", "api", "GET /api/v1/cfb/odds", commit="abc", branch="main"),
        TraceHop("req-1", "verifier", "validate cfb odds", commit="abc", branch="main"),
        TraceHop("req-1", "upstream", "provider response", status="503", commit="abc", branch="main"),
        TraceHop("req-2", "api", "unrelated"),
    ]
    report = correlate_trace(hops, request_id="req-1")
    assert report.complete is True
    assert report.missing_surfaces == ()
    assert report.commit_consistent is True
    assert report.branch_consistent is True
    assert len(report.hops) == 4


def test_trace_calls_out_missing_hop_instead_of_guessing():
    report = correlate_trace(
        [TraceHop("req-1", "api", "GET /route")],
        request_id="req-1",
    )
    assert report.complete is False
    assert set(report.missing_surfaces) == {"streamlit", "verifier", "upstream"}


def test_trace_detects_commit_and_branch_disagreement():
    report = correlate_trace(
        [
            TraceHop("req-1", "api", "request", commit="aaa", branch="main"),
            TraceHop("req-1", "upstream", "response", commit="bbb", branch="staging"),
        ],
        request_id="req-1",
        expected_surfaces=("api", "upstream"),
    )
    assert report.commit_consistent is False
    assert report.branch_consistent is False


def test_production_parity_green_when_exact_source_and_runtime_match():
    report = compare_production_parity(
        ParityIdentity(
            source_branch="main",
            source_commit="abc123",
            runtime_branch="main",
            runtime_commit="abc123",
            expected_runtime_branch="main",
        )
    )
    assert report.status == "ALIGNED"
    assert report.aligned is True
    assert report.issues == ()


def test_production_parity_fails_loudly_on_wrong_deploy_commit():
    report = compare_production_parity(
        ParityIdentity(
            source_branch="main",
            source_commit="new123",
            runtime_branch="mlb-step17b-shared-host-cert",
            runtime_commit="old456",
            expected_runtime_branch="mlb-step17b-shared-host-cert",
        )
    )
    assert report.status == "DRIFT"
    assert report.aligned is False
    assert any("runtime commit differs" in issue for issue in report.issues)


def test_production_parity_detects_wrong_runtime_branch():
    report = compare_production_parity(
        ParityIdentity(
            source_branch="main",
            source_commit="abc",
            runtime_branch="unexpected",
            runtime_commit="abc",
            expected_runtime_branch="certified-runtime",
        )
    )
    assert report.status == "DRIFT"
    assert any("runtime branch drift" in issue for issue in report.issues)


def test_observability_payload_can_build_parity_identity():
    identity = identity_from_observability(
        source_branch="main",
        source_commit="abc",
        runtime={
            "deploy_branch": "runtime-branch",
            "deploy_commit": "def",
            "expected_runtime_branch": "runtime-branch",
            "service": "kyre-sports-api",
            "service_id": "srv-1",
        },
    )
    assert identity.runtime_branch == "runtime-branch"
    assert identity.runtime_commit == "def"
    assert identity.service == "kyre-sports-api"


def test_version_drift_reports_only_real_differences():
    drift = version_drift(
        {"python": "3.12", "schema": "v1", "requests": "2.32"},
        {"python": "3.12", "schema": "v2", "requests": "2.32"},
    )
    assert drift == {"schema": {"expected": "v1", "actual": "v2"}}


def test_trace_and_parity_are_read_only():
    payload = compare_production_parity(
        ParityIdentity("main", "abc", "main", "abc")
    ).as_dict()
    assert payload["projection_weight"] == 0.0
    assert payload["may_modify_projection"] is False
    assert payload["may_modify_source_data"] is False
    assert payload["may_modify_runtime"] is False
    assert payload["network_calls"] is False
