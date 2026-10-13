import pytest

import publish_gate_build as target

SHA = "a" * 40


class DummyClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_require_candidate_accepts_exact_branch(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target.ALLOWED_BRANCH)
    assert target._require_candidate() == (SHA, target.ALLOWED_BRANCH)


def test_require_candidate_rejects_missing_sha(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target.ALLOWED_BRANCH)
    with pytest.raises(RuntimeError, match="FINALIZER_VERCEL_SHA_REQUIRED"):
        target._require_candidate()


def test_require_candidate_rejects_wrong_ref(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", "main")
    with pytest.raises(RuntimeError, match="FINALIZER_VERCEL_REF_MISMATCH"):
        target._require_candidate()


def test_main_reuses_existing_success(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target.ALLOWED_BRANCH)
    monkeypatch.setattr(target, "_run_exact_proof", lambda: [["pytest"]])
    monkeypatch.setattr(target, "_proof_digest", lambda sha, commands: "sha256:" + "1" * 64)
    monkeypatch.setattr(target.Settings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(target.httpx, "Client", lambda timeout=15: DummyClient())
    monkeypatch.setattr(target, "_installation_token", lambda settings, client: "token")
    monkeypatch.setattr(target, "_verify_pr_head", lambda client, token, sha: None)
    monkeypatch.setattr(target, "_existing_success", lambda client, token, sha: True)
    monkeypatch.setattr(target, "_publish_success", lambda *args, **kwargs: pytest.fail("should not publish"))
    assert target.main() == 0


def test_main_publishes_then_requires_readback(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", target.ALLOWED_BRANCH)
    monkeypatch.setattr(target, "_run_exact_proof", lambda: [["pytest"]])
    monkeypatch.setattr(target, "_proof_digest", lambda sha, commands: "sha256:" + "2" * 64)
    monkeypatch.setattr(target.Settings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(target.httpx, "Client", lambda timeout=15: DummyClient())
    monkeypatch.setattr(target, "_installation_token", lambda settings, client: "token")
    monkeypatch.setattr(target, "_verify_pr_head", lambda client, token, sha: None)
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
