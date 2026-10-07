import threading
from types import SimpleNamespace

from runless_proof_plane import executor
from runless_proof_plane.models import FailureClass, SliceEvidence


def test_independent_static_slices_run_in_parallel_with_a_bounded_pool(monkeypatch, tmp_path):
    commands = tuple(
        ("python", "-m", "pytest", "-q", f"tests/fake_slice_{index}.py")
        for index in range(8)
    )
    plan = SimpleNamespace(commands=commands, timeout_seconds=30)
    workspace = SimpleNamespace(path=tmp_path)

    lock = threading.Lock()
    release = threading.Event()
    active = 0
    max_active = 0

    def fake_execute(command, cwd, timeout_seconds):
        nonlocal active, max_active
        assert cwd == tmp_path
        assert timeout_seconds == 30
        with lock:
            active += 1
            max_active = max(max_active, active)
        release.wait(timeout=1.0)
        with lock:
            active -= 1
        return SliceEvidence(
            name=command[-1],
            ok=True,
            command=list(command),
            failure_class=FailureClass.NONE,
        )

    monkeypatch.setattr(executor, "execute_command", fake_execute)
    timer = threading.Timer(0.20, release.set)
    timer.start()
    try:
        evidence = executor.execute_static_slice(plan, workspace)
    finally:
        release.set()
        timer.cancel()

    assert 1 < max_active <= 4
    assert [item.name for item in evidence] == [command[-1] for command in commands]
