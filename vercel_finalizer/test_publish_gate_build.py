import json
from pathlib import Path

import pytest

import publish_gate_build as target

SHA = "a" * 40


class DummyClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _base(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target._target_branch())
    monkeypatch.setattr(target, "_run_exact_proof", lambda: [["pytest"]])
    monkeypatch.setattr(target, "_proof_digest", lambda sha, commands: "sha256:" + "1" * 64)
    monkeypatch.setattr(target.Settings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(target.httpx, "Client", lambda timeout=15: DummyClient())
    monkeypatch.setattr(target, "_installation_token", lambda settings, client: "token")
    monkeypatch.setattr(target, "_verify_pr_head", lambda client, token, sha: None)


def test_target_defaults_preserve_step1_contract(monkeypatch):
    monkeypatch.delenv("FINALIZER_ALLOWED_BRANCH", raising=False)
    monkeypatch.delenv("FINALIZER_PR_NUMBER", raising=False)
    monkeypatch.delenv("FINALIZER_TASK_ID", raising=False)
    assert target._target_branch() == target.ALLOWED_BRANCH
    assert target._target_pr_number() == 1526
    assert target._target_task_id() == "universal-sports-source-finalization-v1-step1"


def test_target_can_bind_step2_without_changing_step1_defaults(monkeypatch):
    monkeypatch.setenv(
        "FINALIZER_ALLOWED_BRANCH",
        "api2-universal-sports-source-finalization-v1-step2-provider-registry",
    )
    monkeypatch.setenv("FINALIZER_PR_NUMBER", "1527")
    monkeypatch.setenv("FINALIZER_TASK_ID", "universal-sports-source-finalization-v1-step2")
    assert target._target_branch().endswith("step2-provider-registry")
    assert target._target_pr_number() == 1527
    assert target._target_task_id() == "universal-sports-source-finalization-v1-step2"


def test_target_rejects_invalid_pr_or_task(monkeypatch):
    monkeypatch.setenv("FINALIZER_PR_NUMBER", "not-a-number")
    with pytest.raises(RuntimeError, match="FINALIZER_PR_NUMBER_INVALID"):
        target._target_pr_number()
    monkeypatch.setenv("FINALIZER_PR_NUMBER", "1527")
    monkeypatch.setenv("FINALIZER_TASK_ID", "../unsafe")
    with pytest.raises(RuntimeError, match="FINALIZER_TASK_ID_INVALID"):
        target._target_task_id()


def test_require_candidate_accepts_exact_branch(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target._target_branch())
    assert target._require_candidate() == (SHA, target._target_branch())


def test_require_candidate_accepts_explicit_step2_branch(monkeypatch):
    branch = "api2-universal-sports-source-finalization-v1-step2-provider-registry"
    monkeypatch.setenv("FINALIZER_ALLOWED_BRANCH", branch)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", branch)
    assert target._require_candidate() == (SHA, branch)


def test_require_candidate_rejects_missing_sha(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target._target_branch())
    with pytest.raises(RuntimeError, match="FINALIZER_VERCEL_SHA_REQUIRED"):
        target._require_candidate()


def test_require_candidate_rejects_wrong_ref(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", "main")
    with pytest.raises(RuntimeError, match="FINALIZER_VERCEL_REF_MISMATCH"):
        target._require_candidate()


def test_run_exact_proof_loads_selected_plan(monkeypatch, tmp_path):
    monkeypatch.setenv("FINALIZER_TASK_ID", "universal-sports-source-finalization-v1-step2")
    calls = []

    class Plan:
        commands = (
            ("python", "-m", "pytest", "-q", "tests/step2.py"),
            ("python", "-m", "py_compile", "devsystem/step2.py"),
        )

    monkeypatch.setattr(target, "load_plan", lambda task_id, root: Plan())
    monkeypatch.setattr(target.subprocess, "run", lambda command, cwd, check: calls.append((command, cwd, check)))
    commands = target._run_exact_proof()
    assert commands[0][0] == target.sys.executable
    assert commands[0][1:] == ["-m", "pytest", "-q", "tests/step2.py"]
    assert commands[1][0] == target.sys.executable
    assert len(calls) == 2
    assert all(call[1] == target.ROOT and call[2] is True for call in calls)


def test_verify_pr_head_uses_explicit_target(monkeypatch):
    monkeypatch.setenv(
        "FINALIZER_ALLOWED_BRANCH",
        "api2-universal-sports-source-finalization-v1-step2-provider-registry",
    )
    monkeypatch.setenv("FINALIZER_PR_NUMBER", "1527")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "head": {
                    "sha": SHA,
                    "ref": "api2-universal-sports-source-finalization-v1-step2-provider-registry",
                }
            }

    class Client:
        def __init__(self):
            self.urls = []

        def get(self, url, headers):
            self.urls.append(url)
            return Response()

    client = Client()
    target._verify_pr_head(client, "token", SHA)
    assert client.urls == [f"https://api.github.com/repos/{target.REPOSITORY}/pulls/1527"]


def test_main_reuses_existing_success(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_existing_success", lambda client, token, sha: True)
    monkeypatch.setattr(target, "_publish_success", lambda *args, **kwargs: pytest.fail("should not publish"))
    assert target.main() == 0


def test_main_publishes_then_requires_readback(monkeypatch):
    _base(monkeypatch)
    states = iter([False, True])
    monkeypatch.setattr(target, "_existing_success", lambda client, token, sha: next(states))
    published = {"count": 0}
    monkeypatch.setattr(
        target,
        "_publish_success",
        lambda *args, **kwargs: published.__setitem__("count", published["count"] + 1),
    )
    assert target.main() == 0
    assert published["count"] == 1


def test_main_candidate_failure_has_owned_exit_code(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target._target_branch())
    assert target.main() == target.PHASE_CANDIDATE


def test_main_proof_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_run_exact_proof", lambda: (_ for _ in ()).throw(RuntimeError("proof")))
    assert target.main() == target.PHASE_PROOF


def test_main_config_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target.Settings, "from_env", classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("config"))))
    assert target.main() == target.PHASE_CONFIG


def test_main_installation_token_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_installation_token", lambda *args: (_ for _ in ()).throw(RuntimeError("token")))
    assert target.main() == target.PHASE_INSTALLATION_TOKEN


def test_main_pr_head_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_verify_pr_head", lambda *args: (_ for _ in ()).throw(RuntimeError("head")))
    assert target.main() == target.PHASE_PR_HEAD


def test_main_existing_check_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_existing_success", lambda *args: (_ for _ in ()).throw(RuntimeError("lookup")))
    assert target.main() == target.PHASE_EXISTING_CHECK


def test_main_publish_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_existing_success", lambda *args: False)
    monkeypatch.setattr(target, "_publish_success", lambda *args: (_ for _ in ()).throw(RuntimeError("publish")))
    assert target.main() == target.PHASE_PUBLISH_CHECK


def test_main_readback_failure_has_owned_exit_code(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(target, "_existing_success", lambda *args: False)
    monkeypatch.setattr(target, "_publish_success", lambda *args: None)
    assert target.main() == target.PHASE_READBACK
