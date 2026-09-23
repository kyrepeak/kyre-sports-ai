import importlib
from pathlib import Path

import nfl_passing_yards_environment_v1 as environment_v1
import nfl_passing_yards_environment_v2 as environment_v2
import nfl_passing_yards_hub_v18 as v18


def test_recursion_guard_repairs_poisoned_environment_builder():
    try:
        canonical = environment_v1.build_game_environment
        assert canonical is not environment_v2.build_game_environment

        environment_v1.build_game_environment = environment_v2.build_game_environment
        assert environment_v1.build_game_environment is environment_v2.build_game_environment

        repaired = v18._repair_environment_base_if_poisoned()
        assert repaired is True
        assert environment_v1.build_game_environment is not environment_v2.build_game_environment

        repaired_again = v18._repair_environment_base_if_poisoned()
        assert repaired_again is False
    finally:
        importlib.reload(environment_v1)


def test_v18_render_repairs_before_running_v17_chain():
    source = Path("nfl_passing_yards_hub_v18.py").read_text()
    render = source.split("def render_nfl_passing_yards_hub() -> None:", 1)[1]
    repair_pos = render.index("_repair_environment_base_if_poisoned()")
    prior_pos = render.index("prior.render_nfl_passing_yards_hub()")
    assert repair_pos < prior_pos


def test_guard_is_runtime_safety_only():
    source = Path("nfl_passing_yards_hub_v18.py").read_text()
    for forbidden in (
        "build_baseline_projection(",
        "build_distribution(",
        "evaluate_market(",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 1",
    ):
        assert forbidden not in source
