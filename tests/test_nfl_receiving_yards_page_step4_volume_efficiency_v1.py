from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_v4_isolated():
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.markdown = lambda *args, **kwargs: None

    fake_prior = types.ModuleType("nfl_receiving_yards_hub_v3")
    fake_prior._player_card_v3 = lambda player, team, opponent: "<article>V3</article>"
    fake_prior._advance_step3_copy = lambda body: body
    fake_prior.render_nfl_receiving_yards_hub = lambda: None

    names = ("streamlit", "nfl_receiving_yards_hub_v3")
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules["streamlit"] = fake_streamlit
    sys.modules["nfl_receiving_yards_hub_v3"] = fake_prior
    try:
        spec = importlib.util.spec_from_file_location(
            "nfl_receiving_yards_hub_v4_isolated",
            ROOT / "nfl_receiving_yards_hub_v4.py",
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


def test_v4_is_additive_over_frozen_v3():
    source = _source("nfl_receiving_yards_hub_v4.py")
    assert "import nfl_receiving_yards_hub_v3 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v3"' in source
    assert "PAGE_BUILD_STEP = 4" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "_ORIGINAL_PLAYER_CARD_V3 = prior._player_card_v3" in source
    assert "prior._player_card_v3 = _player_card_v4" in source
    assert "prior._player_card_v3 = original_card" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step4_profile_contains_receiving_volume_efficiency_fields():
    source = _source("nfl_receiving_yards_hub_v4.py")
    for field in (
        'player.get("receptions_per_game")',
        'player.get("receiving_yards_per_game")',
        'player.get("yards_per_reception")',
        'player.get("targets_per_game")',
        'player.get("sample_games")',
    ):
        assert field in source
    for label in (
        "Receptions / Game",
        "Rec Yards / Game",
        "Yards / Reception",
        "Targets / Game",
        "Catch Rate",
        "Yards / Target",
        "Sample Games",
    ):
        assert label in source
    assert 'aria-label="Receiver volume and efficiency profile"' in source
    assert "40%!important" in source


def test_target_efficiency_uses_only_explicit_targets():
    module = _load_v4_isolated()
    player = {
        "targets_data_available": True,
        "targets": 14,
        "receptions": 9,
        "receiving_yards": 126,
    }
    catch_rate, yards_per_target = module._target_efficiency(player)
    assert catch_rate == 9 / 14 * 100.0
    assert yards_per_target == 9.0

    player["targets_data_available"] = False
    catch_rate, yards_per_target = module._target_efficiency(player)
    assert math.isnan(catch_rate)
    assert math.isnan(yards_per_target)


def test_target_efficiency_fails_closed_for_zero_or_missing_targets():
    module = _load_v4_isolated()
    for targets in (0, None):
        catch_rate, yards_per_target = module._target_efficiency(
            {
                "targets_data_available": True,
                "targets": targets,
                "receptions": 5,
                "receiving_yards": 75,
            }
        )
        assert math.isnan(catch_rate)
        assert math.isnan(yards_per_target)


def test_step4_reserves_defense_h2h_and_later_model_market_steps():
    source = _source("nfl_receiving_yards_hub_v4.py")
    v2 = _source("nfl_receiving_yards_hub_v2.py")
    assert "Opponent pass-defense presentation and player-vs-team history remain reserved for Step 5" in source
    assert "DEFENSE + H2H" in v2
    assert "projection math" in source
    assert "sportsbook markets" in source
    assert "probability, EV, Monte Carlo" in source
    assert "ranking" in source
    assert "wager actions" in source
    assert "opponent_pass_defense" not in source
    assert "build_event_projections(" not in source
    assert "market_for_athlete(" not in source


def test_router_v115_advances_only_receiving_to_v4():
    source = _source("streamlit_memory_lazy_router_v115.py")
    assert "import streamlit_memory_lazy_router_v114 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v114"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v4"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "if _receiving_route_active():" in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_boots_v115_and_preserves_v114_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v115 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V114_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V114_NFL_RECEIVING_YARDS_STEP3_SUMMARY_METRICS_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V115_NFL_RECEIVING_YARDS_STEP4_VOLUME_EFFICIENCY_2026-09-13"' in source


def test_frozen_receiving_v3_router_v114_and_rushing_v15_stay_intact():
    v3 = _source("nfl_receiving_yards_hub_v3.py")
    router_v114 = _source("streamlit_memory_lazy_router_v114.py")
    rushing_v15 = _source("nfl_rushing_yards_hub_v15.py")
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v2"' in v3
    assert "PAGE_BUILD_STEP = 3" in v3
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v113"' in router_v114
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v3"' in router_v114
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v14"' in rushing_v15
    assert 'PHOENIX_TZ_NAME = "America/Phoenix"' in rushing_v15
