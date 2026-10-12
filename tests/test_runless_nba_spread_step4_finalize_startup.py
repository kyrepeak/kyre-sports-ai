import os
from pathlib import Path

from runless_proof_plane import nba_spread_step4_finalize_startup as step4


class FakeState:
    pass


class FakeApp:
    def __init__(self):
        self.state = FakeState()
        self.handlers = {}

    def on_event(self, name):
        def deco(fn):
            self.handlers[name] = fn
            return fn
        return deco


def test_trigger_runs_once_and_records_green(monkeypatch):
    app = FakeApp()
    calls = []
    monkeypatch.setattr(step4, "_execute", lambda: calls.append("run") or {"status": "GREEN"})
    monkeypatch.setenv(step4.ENV_TRIGGER, "1")
    step4.install_startup(app)
    app.handlers["startup"]()
    assert calls == ["run"]
    assert app.state.nba_spread_step4_finalize == {"status": "GREEN"}
    assert step4.ENV_TRIGGER not in os.environ
    app.handlers["startup"]()
    assert calls == ["run"]


def test_failure_is_recorded_not_raised(monkeypatch):
    app = FakeApp()

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(step4, "_execute", boom)
    monkeypatch.setenv(step4.ENV_TRIGGER, "1")
    step4.install_startup(app)
    app.handlers["startup"]()
    assert app.state.nba_spread_step4_finalize["status"] == "FAIL"
    assert app.state.nba_spread_step4_finalize["error"] == "RuntimeError"


def test_bootstrap_installs_step4_finalize():
    text = Path("runless_proof_plane/bootstrap.py").read_text(encoding="utf-8")
    assert "nba_spread_step4_finalize_startup" in text
    assert "install_nba_spread_step4_finalize(app)" in text
