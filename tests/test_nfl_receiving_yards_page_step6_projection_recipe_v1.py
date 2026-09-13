from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_projection_module():
    spec = importlib.util.spec_from_file_location(
        "nfl_receiving_yards_projection_v1_isolated",
        ROOT / "nfl_receiving_yards_projection_v1.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _team() -> dict:
    return {
        "official_team_id": "1",
        "opponent_official_team_id": "2",
        "opponent_pass_defense": {
            "official_team_id": "2",
            "data_available": True,
            "sample_games": 5,
            "receptions_allowed_per_game": 20.0,
            "receiving_yards_allowed_per_game": 200.0,
            "yards_per_reception_allowed": 10.0,
            "receiving_touchdowns_allowed_per_game": 1.0,
            "targets_data_available": False,
            "target_sample_games": 0,
            "targets_allowed_per_game": None,
        },
    }


def _player() -> dict:
    return {
        "official_event_id": "401000001",
        "official_athlete_id": "10",
        "official_team_id": "1",
        "player_name": "Exact Receiver",
        "position": "WR",
        "baseline_season": 2025,
        "sample_games": 5,
        "receptions": 25,
        "receiving_yards": 300.0,
        "yards_per_reception": 12.0,
        "receptions_per_game": 5.0,
        "receiving_yards_per_game": 60.0,
        "receiving_touchdowns": 3,
        "targets_data_available": False,
        "target_sample_games": 0,
        "targets": None,
        "targets_per_game": None,
    }


def _context() -> dict:
    team_a = _team()
    team_a["players"] = [_player()]
    team_b = {
        "official_team_id": "2",
        "opponent_official_team_id": "1",
        "opponent_pass_defense": {
            "official_team_id": "1",
            "data_available": True,
            "sample_games": 5,
            "receptions_allowed_per_game": 22.0,
            "receiving_yards_allowed_per_game": 242.0,
            "yards_per_reception_allowed": 11.0,
            "receiving_touchdowns_allowed_per_game": 1.2,
            "targets_data_available": False,
            "target_sample_games": 0,
            "targets_allowed_per_game": None,
        },
        "players": [
            {
                **_player(),
                "official_athlete_id": "20",
                "official_team_id": "2",
                "receptions": 20,
                "receiving_yards": 220.0,
                "yards_per_reception": 11.0,
                "receptions_per_game": 4.0,
            }
        ],
    }
    return {
        "ready": True,
        "data_available": True,
        "schema_version": "nfl_receiving_yards_context_v1",
        "official_event_id": "401000001",
        "teams": [team_a, team_b],
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "targets_inferred": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def _load_v6_isolated():
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.markdown = lambda *args, **kwargs: None

    fake_prior = types.ModuleType("nfl_receiving_yards_hub_v5")
    fake_prior._player_card_v5 = lambda player, team, opponent: "<article>V5</article>"
    fake_prior._advance_step5_copy = lambda body: body
    fake_prior.render_nfl_receiving_yards_hub = lambda: None

    names = ("streamlit", "nfl_receiving_yards_hub_v5")
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules["streamlit"] = fake_streamlit
    sys.modules["nfl_receiving_yards_hub_v5"] = fake_prior
    try:
        spec = importlib.util.spec_from_file_location(
            "nfl_receiving_yards_hub_v6_isolated",
            ROOT / "nfl_receiving_yards_hub_v6.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, prior in previous.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


def test_projection_uses_proven_65_35_efficiency_blend():
    module = _load_projection_module()
    result = module.build_player_projection(
        official_event_id="401000001",
        team=_team(),
        player=_player(),
    )
    assert result["ready"] is True
    assert math.isclose(result["expected_receptions"], 5.0)
    assert math.isclose(result["expected_yards_per_reception"], 11.3)
    assert math.isclose(result["projection_yards"], 56.5)
    assert result["formula"] == "expected_receptions × expected_yards_per_reception"
    assert result["sportsbook_influence"] == 0.0
    assert result["targets_used"] is False
    weights = {row["key"]: row["normalized_weight"] for row in result["efficiency_components"]}
    assert math.isclose(weights["player_yards_per_reception"], 0.65)
    assert math.isclose(weights["opponent_yards_per_reception_allowed"], 0.35)


def test_projection_does_not_require_or_infer_targets():
    module = _load_projection_module()
    player = _player()
    assert player["targets_data_available"] is False
    assert player["targets"] is None
    result = module.build_player_projection(
        official_event_id="401000001",
        team=_team(),
        player=player,
    )
    assert result["ready"] is True
    assert result["targets_used"] is False


def test_projection_fails_closed_on_exact_identity_mismatch():
    module = _load_projection_module()
    player = _player()
    player["official_team_id"] = "999"
    result = module.build_player_projection(
        official_event_id="401000001",
        team=_team(),
        player=player,
    )
    assert result["ready"] is False
    assert "identity" in result["reason"]
    assert math.isnan(result["projection_yards"])
    assert result["sportsbook_influence"] == 0.0


def test_projection_fails_closed_on_opponent_identity_mismatch():
    module = _load_projection_module()
    team = _team()
    team["opponent_pass_defense"]["official_team_id"] = "3"
    result = module.build_player_projection(
        official_event_id="401000001",
        team=team,
        player=_player(),
    )
    assert result["ready"] is False
    assert "identity mismatch" in result["reason"]


def test_event_projection_requires_frozen_context_safety_contract():
    module = _load_projection_module()
    context = _context()
    good = module.build_event_projections(context)
    assert good["ready"] is True
    assert good["projection_count"] == 2
    assert good["sportsbook_influence"] == 0.0
    assert good["market_enabled"] is False
    assert good["probability_enabled"] is False
    assert good["monte_carlo_enabled"] is False

    context["sportsbook_influence"] = 0.01
    bad = module.build_event_projections(context)
    assert bad["ready"] is False
    assert "safety contract" in bad["reason"]


def test_v6_surface_is_additive_over_frozen_v5_and_advances_to_60_percent():
    source = _source("nfl_receiving_yards_hub_v6.py")
    assert "import nfl_receiving_yards_hub_v5 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v5"' in source
    assert "PAGE_BUILD_STEP = 6" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "60%!important" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MARKET-BLIND PROJECTION" in source
    assert "FanDuel markets remain locked for Step 8" in source


def test_v6_recipe_html_shows_projection_formula_weights_and_safety():
    module = _load_v6_isolated()
    html = module._projection_recipe_html(_player(), _team())
    assert "56.5 YDS" in html
    assert "5" in html
    assert "11.3" in html
    assert "65% normalized blend weight" in html
    assert "35% normalized blend weight" in html
    assert "sportsbook influence 0.0%" in html
    assert "targets used: NO" in html


def test_router_v117_advances_only_receiving_to_v6():
    source = _source("streamlit_memory_lazy_router_v117.py")
    assert "import streamlit_memory_lazy_router_v116 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v116"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v6"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_boots_v117_and_preserves_v116_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v117 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V116_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V116_NFL_RECEIVING_YARDS_STEP5_DEFENSE_H2H_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V117_NFL_RECEIVING_YARDS_STEP6_PROJECTION_RECIPE_2026-09-13"' in source


def test_frozen_v5_rushing_and_passing_owners_remain_untouched_by_step6_contract():
    v5 = _source("nfl_receiving_yards_hub_v5.py")
    rushing_v15 = _source("nfl_rushing_yards_hub_v15.py")
    router_v116 = _source("streamlit_memory_lazy_router_v116.py")
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v4"' in v5
    assert "PAGE_BUILD_STEP = 5" in v5
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v14"' in rushing_v15
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v5"' in router_v116
