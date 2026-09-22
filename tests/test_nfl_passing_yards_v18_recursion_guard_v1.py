from __future__ import annotations

import nfl_passing_yards_defense_v1 as defense_v1
import nfl_passing_yards_environment_v1 as environment_v1
import nfl_passing_yards_hub_v17 as v17
import nfl_passing_yards_hub_v18 as v18
import nfl_passing_yards_pressure_v1 as pressure_v1


def test_v18_isolates_v17_builder_overrides_from_shared_v1_modules(monkeypatch):
    original_defense_builder = defense_v1.build_pass_defense_profile
    original_pressure_builder = pressure_v1.build_pressure_matchup
    original_environment_builder = environment_v1.build_game_environment

    assert v17.step7_ui.defense is defense_v1
    assert v17.step7_ui.pressure is pressure_v1
    assert v17.step7_ui.environment is environment_v1

    observed = {"called": False}

    def fake_v16_render():
        observed["called"] = True

        # V17 has installed its bridge builders at this point, but V18 must make
        # those writes land on proxies rather than the shared V1 modules that
        # V2/V3 delegate back into.
        assert v17.step7_ui.defense is not defense_v1
        assert v17.step7_ui.pressure is not pressure_v1
        assert v17.step7_ui.environment is not environment_v1
        assert getattr(v17.step7_ui.defense, "_wrapped", None) is defense_v1
        assert getattr(v17.step7_ui.pressure, "_wrapped", None) is pressure_v1
        assert getattr(v17.step7_ui.environment, "_wrapped", None) is environment_v1

        assert v17.step7_ui.defense.build_pass_defense_profile is not original_defense_builder
        assert v17.step7_ui.pressure.build_pressure_matchup is not original_pressure_builder
        assert v17.step7_ui.environment.build_game_environment is not original_environment_builder

        # The real shared base modules must stay untouched, otherwise the early-
        # season bridge calls itself recursively through its own V1 dependency.
        assert defense_v1.build_pass_defense_profile is original_defense_builder
        assert pressure_v1.build_pressure_matchup is original_pressure_builder
        assert environment_v1.build_game_environment is original_environment_builder

    monkeypatch.setattr(v17.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(v17.prior, "render_nfl_passing_yards_hub", fake_v16_render)

    v18.render_nfl_passing_yards_hub()

    assert observed["called"] is True
    assert v17.step7_ui.defense is defense_v1
    assert v17.step7_ui.pressure is pressure_v1
    assert v17.step7_ui.environment is environment_v1
    assert defense_v1.build_pass_defense_profile is original_defense_builder
    assert pressure_v1.build_pressure_matchup is original_pressure_builder
    assert environment_v1.build_game_environment is original_environment_builder


def test_v35_routes_passing_yards_to_v18(monkeypatch):
    import nfl_hub_v35 as hub

    called = {"count": 0}

    def fake_render():
        called["count"] += 1

    monkeypatch.setattr(v18, "render_nfl_passing_yards_hub", fake_render)
    hub.render_nfl_hub("Passing Yards")

    assert called["count"] == 1
