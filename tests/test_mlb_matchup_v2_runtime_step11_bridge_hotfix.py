from __future__ import annotations

import inspect
from types import SimpleNamespace

import mlb_matchup_player_v35 as player


def test_step12_runtime_bridge_falls_back_when_private_step11_builder_is_missing(monkeypatch):
    foundation = {"player_name": "Runtime Test", "valid_slot": True, "starter_id": 99}
    profiles = {
        "step1": foundation,
        "step2": {"hitter": True},
        "step3": {"starter": True},
        "step4": {"platoon": True},
        "step5": {"pitch": True},
        "step6": {"batted": True},
        "step7": {"environment": True},
        "step8": {"bullpen": True},
        "step9": {"opportunity": True},
        "step10": {"recent": True},
    }

    monkeypatch.setattr(player, "step11", SimpleNamespace())
    monkeypatch.setattr(player.step1, "_build_foundation", lambda games_df: profiles["step1"])
    monkeypatch.setattr(player.step2, "_build_step2", lambda games_df: profiles["step2"])
    monkeypatch.setattr(player.step3, "_build_step3", lambda games_df: profiles["step3"])
    monkeypatch.setattr(player.step4, "_build_step4", lambda games_df: profiles["step4"])
    monkeypatch.setattr(player.step5, "_build_step5", lambda games_df: profiles["step5"])
    monkeypatch.setattr(player.step6, "_build_step6", lambda games_df: profiles["step6"])
    monkeypatch.setattr(player.step7, "_build_step7", lambda games_df: profiles["step7"])
    monkeypatch.setattr(player.step8, "_build_step8", lambda games_df: profiles["step8"])
    monkeypatch.setattr(player.step9, "_build_step9", lambda games_df: profiles["step9"])
    monkeypatch.setattr(player.step10, "_build_step10", lambda games_df: profiles["step10"])

    captured = {}

    def fake_probability(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"probability_status": "READY_RAW", "p1_plus": 0.70, "player_name": "Runtime Test"}

    monkeypatch.setattr(player.raw_probability, "build_probability_profile", fake_probability)
    monkeypatch.setattr(
        player.calibration,
        "build_final_intelligence",
        lambda raw, persist=True: {**raw, "final_status": "FINAL_READY", "persist": persist},
    )

    result = player._build_step12(object(), simulations=1234, persist=False)

    assert result["final_status"] == "FINAL_READY"
    assert result["persist"] is False
    assert captured["kwargs"]["simulations"] == 1234
    assert len(captured["args"]) == 10
    assert captured["args"][0] is foundation


def test_runtime_bridge_prefers_certified_step11_builder_when_available(monkeypatch):
    raw = {"probability_status": "READY_RAW", "p1_plus": 0.66}
    calls = {"count": 0}

    def certified_builder(games_df, simulations=None):
        calls["count"] += 1
        calls["simulations"] = simulations
        return raw

    monkeypatch.setattr(player, "step11", SimpleNamespace(_build_step11=certified_builder))
    monkeypatch.setattr(
        player.calibration,
        "build_final_intelligence",
        lambda profile, persist=True: {"raw": profile, "persist": persist},
    )
    monkeypatch.setattr(
        player,
        "_build_step11_fallback",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fallback should not run")),
    )

    result = player._build_step12(object(), simulations=77, persist=False)

    assert calls == {"count": 1, "simulations": 77}
    assert result == {"raw": raw, "persist": False}


def test_runtime_bridge_is_defensive_and_keeps_single_simulation_path():
    source = inspect.getsource(player)
    assert 'getattr(step11, "_build_step11", None)' in source
    assert "def _build_step11_fallback" in source
    assert "raw_probability.build_probability_profile" in source
    render_source = inspect.getsource(player.render_player_layer)
    assert "builder(games_df) if callable(builder) else _build_step11_fallback(games_df)" in render_source
    assert render_source.count("calibration.build_final_intelligence") == 1
