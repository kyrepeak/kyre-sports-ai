from devsystem import failure_packet_v1
from devsystem import failure_triage_v1
from devsystem.wait_state_machine_v1 import (
    VERSION,
    classify_wait,
    self_test,
    state_change_allows_recheck,
)


def test_self_test_green_and_read_only():
    result = self_test()
    assert result["version"] == VERSION
    assert result["status"] == "GREEN"
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False


def test_deployment_in_flight_is_wait_not_failure():
    report = failure_triage_v1.triage({
        "production-verification": {
            "result": "failure",
            "evidence": "deployment phase=ACTIVATING; deployment still progressing",
        }
    })
    assert report["status"] == "WAITING"
    assert report["failure_count"] == 0
    assert report["wait_count"] == 1
    assert report["primary"] is None
    waiting = report["waits"][0]
    assert waiting["wait_state"] == "WAITING_FOR_DEPLOYMENT_EVENT"
    assert waiting["blind_retry_allowed"] is False
    assert waiting["recheck_policy"] == "EVENT_DRIVEN_STATE_CHANGE_ONLY"


def test_stale_production_identity_waits_for_sha_change():
    expected = "a" * 40
    observed = "b" * 40
    report = failure_triage_v1.triage({
        "production-verification": {
            "result": "failure",
            "evidence": f"stale deployment expected={expected} actual={observed}",
        }
    })
    waiting = report["waits"][0]
    assert report["status"] == "WAITING"
    assert waiting["wait_state"] == "WAITING_FOR_EXACT_DEPLOYMENT"
    assert "production SHA changes" in waiting["wake_condition"]


def test_network_upstream_waits_without_entering_repair_queue():
    packet = failure_packet_v1.build_packet({
        "data-provider-check": {
            "result": "failure",
            "evidence": "503 Service Unavailable from upstream API",
        }
    })
    assert packet["status"] == "WAITING"
    assert packet["triage"]["failure_count"] == 0
    assert packet["triage"]["wait_count"] == 1
    assert packet["root_cause_collapse"]["decision"] == "NO_FAILURES"
    assert packet["root_cause_collapse"]["repair_queue"] == []


def test_assertion_remains_real_failure():
    report = failure_triage_v1.triage({
        "cfb-critical": {
            "result": "failure",
            "evidence": "AssertionError expected official ESPN event ID",
        }
    })
    assert report["status"] == "FAILURES_FOUND"
    assert report["failure_count"] == 1
    assert report["wait_count"] == 0
    assert report["primary"]["job"] == "cfb-critical"
    assert report["primary"]["evidence_signal"] == "test-assertion"


def test_mixed_wait_and_real_failure_preserves_real_root():
    packet = failure_packet_v1.build_packet({
        "production-verification": {
            "result": "failure",
            "evidence": "deployment phase=BUILDING; deployment still progressing",
        },
        "cfb-critical": {
            "result": "failure",
            "evidence": "AssertionError expected frozen contract",
        },
    })
    assert packet["status"] == "FAILURES_FOUND"
    assert packet["triage"]["wait_count"] == 1
    assert packet["triage"]["failure_count"] == 1
    assert packet["root_cause_collapse"]["root_count"] == 1
    assert packet["root_cause_collapse"]["primary_root"]["job"] == "cfb-critical"
    assert [item["job"] for item in packet["root_cause_collapse"]["repair_queue"]] == ["cfb-critical"]


def test_unchanged_wait_state_never_authorizes_recheck():
    first = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text="stale deployment expected=" + "a" * 40 + " actual=" + "b" * 40,
    )
    same = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text="stale deployment expected=" + "a" * 40 + " actual=" + "b" * 40,
    )
    changed = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text="stale deployment expected=" + "a" * 40 + " actual=" + "a" * 40,
    )
    assert state_change_allows_recheck(first["state_token"], same["state_token"]) is False
    assert state_change_allows_recheck(first["state_token"], changed["state_token"]) is True
