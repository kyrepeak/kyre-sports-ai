from __future__ import annotations

from pathlib import Path

from sports_api.monster_incident_autopacket_v1 import (
    IncidentInput,
    build_incident_packet,
)
from sports_api.monster_performance_profiler_v1 import SpanSample
from sports_api.monster_runtime_capture_v1 import capture_response
from sports_api.monster_runtime_trace_v1 import ParityIdentity, TraceHop

ROOT = Path(__file__).resolve().parents[1]

KNOWN_SIGNATURE = "cfb ou cold start eagerly imports historical router spine before active page"


def test_autopacket_combines_real_monster_signals_in_one_case_file():
    artifact = capture_response(
        route_key="cfb_odds",
        url="https://api.test/api/v1/cfb/odds",
        status_code=503,
        headers={"X-Request-ID": "req-1"},
        json_body={"detail": "CFB odds endpoint is not ready: market identity coverage is incomplete"},
    )
    incident = IncidentInput(
        title="CFB page slow and odds protected",
        symptom="Cold load is slow and CFB odds returned protected 503",
        target="sports_api/monster_incident_autopacket_v1.py",
        request_id="req-1",
        failure_signature=KNOWN_SIGNATURE,
        sport="CFB",
        route="cfb-over-under",
        surface="streamlit",
        total_ms=3600,
        spans=(
            SpanSample("bootstrap.router", 2800, category="import"),
            SpanSample("render.cards", 400, category="render"),
        ),
        trace_hops=(
            TraceHop("req-1", "streamlit", "page", commit="abc", branch="main"),
            TraceHop("req-1", "api", "odds", commit="abc", branch="main"),
            TraceHop("req-1", "verifier", "contract", commit="abc", branch="main"),
            TraceHop("req-1", "upstream", "503", status="503", commit="abc", branch="main"),
        ),
        parity_identity=ParityIdentity("main", "abc", "main", "abc", "main"),
        replay_artifact=artifact,
        recent_commits=("abc Fix prior issue",),
        render_log_lines=("KYRE_SLOW_REQUEST req-1",),
        posthog_context={"issue": "known error group"},
    )
    packet = build_incident_packet(incident, repo_root=ROOT)

    assert packet["signals"]["performance"]["grade"] == "CRITICAL"
    assert packet["signals"]["performance"]["bottleneck"] == "bootstrap.router"
    assert packet["signals"]["failure_memory"]["status"] == "FOUND"
    assert packet["signals"]["failure_memory"]["exact"] is True
    assert packet["signals"]["dependency"]["status"] == "OK"
    assert packet["signals"]["test_matrix"]["passed"] is True
    assert packet["signals"]["test_matrix"]["scenario_count"] >= 20
    assert packet["signals"]["trace"]["complete"] is True
    assert packet["signals"]["parity"]["status"] == "ALIGNED"
    assert packet["signals"]["replay"]["fingerprint"].startswith("REPLAY-")
    assert "cfb-critical" in packet["recommended_tests"]
    assert "devsystem-final-gate" in packet["recommended_tests"]


def test_autopacket_prioritizes_parity_drift_before_code_change():
    packet = build_incident_packet(
        IncidentInput(
            title="Wrong deploy",
            symptom="Production differs from source",
            parity_identity=ParityIdentity(
                "main",
                "new",
                "runtime-branch",
                "old",
                "runtime-branch",
            ),
        ),
        repo_root=ROOT,
    )
    assert packet["signals"]["parity"]["status"] == "DRIFT"
    assert packet["priority_actions"][0]["priority"] == "P0"
    assert "parity drift" in packet["priority_actions"][0]["action"].lower()


def test_autopacket_does_not_fuzzy_match_unknown_failure_signature():
    packet = build_incident_packet(
        IncidentInput(
            title="Unknown",
            symptom="Looks vaguely like an old problem",
            failure_signature="cfb cold startup seems a little slow today",
        ),
        repo_root=ROOT,
    )
    assert packet["signals"]["failure_memory"]["status"] == "NOT_FOUND"
    assert packet["signals"]["failure_memory"]["found"] is False


def test_autopacket_clips_external_evidence_and_remains_read_only():
    packet = build_incident_packet(
        IncidentInput(
            title="Evidence",
            symptom="test",
            recent_commits=("x" * 5000,),
            render_log_lines=("y" * 5000,),
            posthog_context={"detail": "z" * 5000},
        ),
        repo_root=ROOT,
    )
    assert len(packet["evidence"]["recent_commits"][0]) <= 1500
    assert len(packet["evidence"]["render_log_lines"][0]) <= 1500
    assert len(packet["evidence"]["posthog_context"]["detail"]) <= 1500
    assert packet["protections"] == {
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "may_modify_source_data": False,
        "may_modify_runtime": False,
        "network_calls": False,
        "auto_fix": False,
    }


def test_autopacket_without_enough_evidence_says_reproduce_first():
    packet = build_incident_packet(
        IncidentInput(title="Unknown", symptom="Something broke"),
        repo_root=ROOT,
    )
    assert "reproduce" in packet["priority_actions"][0]["action"].lower()
