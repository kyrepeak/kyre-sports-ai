from copy import deepcopy
import json

import pytest

from scripts import build_monster_production_certification_snapshot_v1 as monster


COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
OBSERVED_AT = "2026-09-15T05:30:00+00:00"
RUNTIME_BRANCH = "mlb-step17b-shared-host-cert"


def _inputs():
    return {
        "github": {
            "branch": RUNTIME_BRANCH,
            "commit": COMMIT_A,
        },
        "render": {
            "branch": RUNTIME_BRANCH,
            "commit": COMMIT_A,
            "status": "live",
            "auto_deploy": "no",
        },
        "health": {
            "status": "ok",
            "service": "kyre-sports-api",
            "deployment": {
                "branch": RUNTIME_BRANCH,
                "commit": COMMIT_A,
                "branch_aligned": True,
            },
        },
        "readiness": {
            "status": "ready",
            "checks": {
                "process_running": True,
                "python_runtime": True,
                "deployment_identity_available": True,
                "runtime_branch_alignment": True,
            },
            "deployment": {
                "branch": RUNTIME_BRANCH,
                "commit": COMMIT_A,
                "canonical_source_branch": "main",
                "expected_runtime_branch": RUNTIME_BRANCH,
                "aligned": True,
            },
        },
        "guards": {
            "devsystem-final-gate": "green",
            "permanent-freeze": "green",
            "regression-shield": "green",
        },
    }


def _build(values=None):
    values = values or _inputs()
    return monster.build_snapshot(
        github=values["github"],
        render=values["render"],
        health=values["health"],
        readiness=values["readiness"],
        guards=values["guards"],
        observed_at=OBSERVED_AT,
    )


def test_green_when_commit_identity_readiness_and_guards_agree():
    snapshot = _build()

    assert snapshot["version"] == "MONSTER_PRODUCTION_CERTIFICATION_V1"
    assert snapshot["state"] == "GREEN"
    assert snapshot["certified"] is True
    assert snapshot["identity"] == {
        "github_branch": RUNTIME_BRANCH,
        "github_commit": COMMIT_A,
        "render_branch": RUNTIME_BRANCH,
        "render_commit": COMMIT_A,
        "health_branch": RUNTIME_BRANCH,
        "health_commit": COMMIT_A,
    }
    assert snapshot["render_auto_deploy"] == "no"
    assert snapshot["reasons"] == []
    assert monster.certification_exit_code(snapshot) == 0


def test_production_lag_when_render_and_runtime_agree_but_not_with_github():
    values = _inputs()
    values["render"]["commit"] = COMMIT_B
    values["health"]["deployment"]["commit"] = COMMIT_B
    values["readiness"]["deployment"]["commit"] = COMMIT_B

    snapshot = _build(values)

    assert snapshot["state"] == "PRODUCTION_LAG"
    assert snapshot["certified"] is False
    assert snapshot["identity"]["render_commit"] == COMMIT_B
    assert monster.certification_exit_code(snapshot) == 1


@pytest.mark.parametrize("status", ["update_failed", "build_failed", "canceled", "deactivated"])
def test_failed_or_non_live_render_deploy_blocks_certification(status):
    values = _inputs()
    values["render"]["status"] = status

    snapshot = _build(values)

    assert snapshot["state"] == "DEPLOY_FAILED"
    assert snapshot["certified"] is False


def test_render_and_health_commit_disagreement_is_identity_conflict():
    values = _inputs()
    values["health"]["deployment"]["commit"] = COMMIT_B
    values["readiness"]["deployment"]["commit"] = COMMIT_B

    snapshot = _build(values)

    assert snapshot["state"] == "IDENTITY_CONFLICT"
    assert snapshot["certified"] is False


def test_intended_github_runtime_branch_must_match_render_branch():
    values = _inputs()
    values["github"]["branch"] = "main"

    snapshot = _build(values)

    assert snapshot["state"] == "IDENTITY_CONFLICT"
    assert snapshot["certified"] is False
    assert "branch" in " ".join(snapshot["reasons"]).lower()


@pytest.mark.parametrize("health_status", ["error", "down", "unknown", None])
def test_unhealthy_runtime_blocks_certification(health_status):
    values = _inputs()
    values["health"]["status"] = health_status

    snapshot = _build(values)

    assert snapshot["state"] == "RUNTIME_PROOF_FAILED"
    assert snapshot["certified"] is False


def test_not_ready_when_runtime_branch_alignment_is_false():
    values = _inputs()
    values["readiness"]["checks"]["runtime_branch_alignment"] = False
    values["readiness"]["deployment"]["aligned"] = False

    snapshot = _build(values)

    assert snapshot["state"] == "NOT_READY"
    assert snapshot["certified"] is False


def test_not_ready_when_readiness_status_is_not_ready():
    values = _inputs()
    values["readiness"]["status"] = "starting"

    snapshot = _build(values)

    assert snapshot["state"] == "NOT_READY"
    assert snapshot["certified"] is False


@pytest.mark.parametrize(
    "mutator",
    [
        lambda values: values["github"].pop("commit"),
        lambda values: values["render"].pop("commit"),
        lambda values: values["render"].pop("auto_deploy"),
        lambda values: values["health"].pop("deployment"),
        lambda values: values["readiness"].pop("checks"),
        lambda values: values.update(guards={}),
        lambda values: values["github"].update(commit="not-a-sha"),
    ],
)
def test_missing_or_malformed_required_evidence_fails_closed_to_unknown(mutator):
    values = _inputs()
    mutator(values)

    snapshot = _build(values)

    assert snapshot["state"] == "UNKNOWN"
    assert snapshot["certified"] is False
    assert snapshot["reasons"]


def test_guard_failure_blocks_otherwise_aligned_identity():
    values = _inputs()
    values["guards"]["permanent-freeze"] = "failure"

    snapshot = _build(values)

    assert snapshot["state"] == "GUARD_FAILED"
    assert snapshot["certified"] is False
    assert snapshot["guards"]["permanent-freeze"] == "failure"


def test_auto_deploy_must_remain_off_for_certification():
    values = _inputs()
    values["render"]["auto_deploy"] = "yes"

    snapshot = _build(values)

    assert snapshot["state"] == "GUARD_FAILED"
    assert snapshot["certified"] is False
    assert "auto-deploy" in " ".join(snapshot["reasons"]).lower()


def test_same_normalized_inputs_produce_identical_snapshot():
    first = _build()
    second = _build()

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_input_mappings_are_not_mutated():
    values = _inputs()
    before = deepcopy(values)

    _build(values)

    assert values == before


def test_http_policy_is_read_only_get_only():
    assert monster.ALLOWED_HTTP_METHODS == frozenset({"GET"})


def test_normalize_render_evidence_uses_service_branch_and_live_deploy_commit():
    service = {
        "id": "srv-test",
        "name": "kyre-sports-api",
        "branch": RUNTIME_BRANCH,
        "autoDeploy": "no",
    }
    deploy = {
        "id": "dep-test",
        "status": "live",
        "commit": {"id": COMMIT_A, "message": "certified runtime"},
    }

    normalized = monster.normalize_render_evidence(service, deploy)

    assert normalized == {
        "branch": RUNTIME_BRANCH,
        "commit": COMMIT_A,
        "status": "live",
        "service_id": "srv-test",
        "deploy_id": "dep-test",
        "auto_deploy": "no",
    }


def test_collect_runtime_health_reads_only_health_and_ready_endpoints():
    calls = []
    health = _inputs()["health"]
    readiness = _inputs()["readiness"]

    def fake_fetch(url):
        calls.append(url)
        if url.endswith("/health"):
            return deepcopy(health)
        if url.endswith("/health/ready"):
            return deepcopy(readiness)
        raise AssertionError(f"unexpected URL: {url}")

    result = monster.collect_runtime_health(
        "https://kyre-sports-api.onrender.com/",
        fetch_json=fake_fetch,
    )

    assert result == {"health": health, "readiness": readiness}
    assert calls == [
        "https://kyre-sports-api.onrender.com/health",
        "https://kyre-sports-api.onrender.com/health/ready",
    ]


def test_get_json_uses_get_and_accepts_only_object_json():
    seen = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size):
            seen["read_size"] = size
            return b'{"status":"ok"}'

    def opener(request, timeout):
        seen["method"] = request.get_method()
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response()

    payload = monster.get_json("https://example.test/health", opener=opener)

    assert payload == {"status": "ok"}
    assert seen["method"] == "GET"
    assert seen["url"] == "https://example.test/health"
    assert seen["timeout"] == monster.HTTP_TIMEOUT_SECONDS
    assert seen["read_size"] == monster.MAX_JSON_BYTES + 1


def test_get_json_rejects_non_object_payload():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size):
            return b"[]"

    with pytest.raises(RuntimeError, match="non-object JSON"):
        monster.get_json("https://example.test/health", opener=lambda request, timeout: Response())


def test_runtime_source_branch_can_be_green_independently_of_canonical_main_name():
    values = _inputs()
    values["github"] = {
        "branch": RUNTIME_BRANCH,
        "commit": COMMIT_A,
        "canonical_branch": "main",
        "canonical_commit": COMMIT_B,
    }

    snapshot = _build(values)

    assert snapshot["state"] == "GREEN"
    assert snapshot["certified"] is True
    assert snapshot["identity"]["github_branch"] == RUNTIME_BRANCH
