import pytest

import publish_gate_build as target

SHA = "a" * 40


def _identity(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setenv("FINALIZER_TASK_ID", "runless-dynamic-finalization-authority-v1")
    monkeypatch.setenv("FINALIZER_WORKSTREAM", "runless-dynamic-finalization-authority-v1")
    monkeypatch.setenv("FINALIZER_FENCING_GENERATION", "7")


def test_no_historical_defaults(monkeypatch):
    for key in ("FINALIZER_TASK_ID", "FINALIZER_WORKSTREAM", "FINALIZER_FENCING_GENERATION"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError):
        target._target_task_id()
    with pytest.raises(RuntimeError):
        target._target_workstream()
    with pytest.raises(RuntimeError):
        target._fencing_generation()


def test_dynamic_identity(monkeypatch):
    _identity(monkeypatch)
    assert target._target_task_id() == "runless-dynamic-finalization-authority-v1"
    assert target._target_workstream() == "runless-dynamic-finalization-authority-v1"
    assert target._fencing_generation() == 7
    assert target._require_candidate() == SHA


def test_rejects_invalid_task_and_fence(monkeypatch):
    _identity(monkeypatch)
    monkeypatch.setenv("FINALIZER_TASK_ID", "../unsafe")
    with pytest.raises(RuntimeError, match="FINALIZER_TASK_ID_INVALID"):
        target._target_task_id()
    monkeypatch.setenv("FINALIZER_TASK_ID", "safe")
    monkeypatch.setenv("FINALIZER_FENCING_GENERATION", "bad")
    with pytest.raises(RuntimeError, match="FINALIZER_FENCING_GENERATION_INVALID"):
        target._fencing_generation()


def test_run_exact_proof_loads_selected_plan(monkeypatch):
    _identity(monkeypatch)
    calls = []

    class Plan:
        commands = (("python", "-m", "pytest", "-q", "tests/example.py"),)

    monkeypatch.setattr(target, "load_plan", lambda task_id, root: Plan())
    monkeypatch.setattr(target.subprocess, "run", lambda command, cwd, check: calls.append((command, cwd, check)))
    commands = target._run_exact_proof()
    assert commands[0][0] == target.sys.executable
    assert calls[0][1] == target.ROOT
    assert calls[0][2] is True


def test_main_runs_proof_without_publishing_gate(monkeypatch):
    _identity(monkeypatch)
    monkeypatch.setattr(target, "_run_exact_proof", lambda: [["pytest"]])
    monkeypatch.setattr(target, "_proof_digest", lambda sha, commands: "sha256:" + "1" * 64)
    assert target.main() == 0


def test_preview_without_identity_skips_build_proof(monkeypatch):
    for key in ("FINALIZER_TASK_ID", "FINALIZER_WORKSTREAM", "FINALIZER_FENCING_GENERATION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("VERCEL_ENV", "preview")
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    monkeypatch.setattr(target, "_run_exact_proof", lambda: pytest.fail("preview must not execute task proof"))
    assert target.main() == 0


def test_production_without_identity_still_fails_closed(monkeypatch):
    for key in ("FINALIZER_TASK_ID", "FINALIZER_WORKSTREAM", "FINALIZER_FENCING_GENERATION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", SHA)
    with pytest.raises(RuntimeError, match="FINALIZER_TASK_ID_REQUIRED"):
        target.main()
