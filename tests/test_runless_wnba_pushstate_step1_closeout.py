from __future__ import annotations

from runless_proof_plane.wnba_pushstate_step1_closeout import (
    STEP1_ARTIFACTS,
    publish_candidate_gate,
    publish_candidate_gate_from_env,
)

CANDIDATE = "ab3fdb3e544500366618bea71bd29976307f0c9f"
BASE = "f8fe7aef9f9519750aaa9053716d2059c9bbdb83"


class FakeClient:
    def __init__(self):
        self.published = []

    def request(self, method, path, **kwargs):
        if method == "GET" and path == "/pulls/1416":
            return {
                "state": "open",
                "head": {"sha": CANDIDATE},
                "base": {"ref": "main", "sha": BASE},
            }
        if method == "GET" and path == "/pulls/1416/files?per_page=100":
            return [{"filename": path} for path in STEP1_ARTIFACTS]
        raise AssertionError((method, path, kwargs))

    def branch_sha(self, branch):
        assert branch == "main"
        return BASE

    def tree_blobs(self, sha):
        assert sha == CANDIDATE
        return {
            path: f"{index + 1:040x}"
            for index, path in enumerate(STEP1_ARTIFACTS)
        }

    def publish_check(self, sha, name, conclusion, output):
        self.published.append((sha, name, conclusion, output))
        return {"id": 777, "conclusion": conclusion}


def proof_evidence():
    return {
        "worker_service_id": "srv-db2l7vad0e5s73bhc8pg",
        "worker_deploy_id": "dep-db2l7vqd0e5s73bhcbe0",
        "test_result": "1 passed in 1.89s",
        "cert_token": "RUNLESS_WNBA_PUSHSTATE_STEP1_GREEN",
        "owner": "_pin_deep_wnba_shell_route",
        "feedback_loop_proven": True,
    }


def test_candidate_bridge_publishes_exact_runless_gate_only_after_identity_checks():
    client = FakeClient()
    result = publish_candidate_gate(
        client,
        candidate_sha=CANDIDATE,
        base_sha=BASE,
        pr_number=1416,
        evidence=proof_evidence(),
    )

    assert result["status"] == "GREEN"
    assert result["candidate_sha"] == CANDIDATE
    assert result["check_id"] == 777
    assert len(result["receipt_digest"]) == 64
    assert client.published[0][0] == CANDIDATE
    assert client.published[0][1] == "runless-final-gate"
    assert client.published[0][2] == "success"


def test_env_handoff_requires_explicit_arm_and_exact_proof_metadata(monkeypatch):
    client = FakeClient()
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START", "1")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_SHA", CANDIDATE)
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_BASE_SHA", BASE)
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_PR", "1416")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_WORKER_SERVICE_ID", "srv-db2l7vad0e5s73bhc8pg")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_WORKER_DEPLOY_ID", "dep-db2l7vqd0e5s73bhcbe0")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_TEST_RESULT", "1 passed in 1.89s")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_CERT_TOKEN", "RUNLESS_WNBA_PUSHSTATE_STEP1_GREEN")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_OWNER", "_pin_deep_wnba_shell_route")
    monkeypatch.setenv("RPP_WNBA_PUSHSTATE_STEP1_FEEDBACK_LOOP_PROVEN", "1")

    result = publish_candidate_gate_from_env(client)

    assert result["status"] == "GREEN"
    assert result["candidate_sha"] == CANDIDATE
    assert client.published[0][1] == "runless-final-gate"
