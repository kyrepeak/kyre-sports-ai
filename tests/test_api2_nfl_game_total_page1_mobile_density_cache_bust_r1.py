from __future__ import annotations

from pathlib import Path
import importlib.util


def test_game_total_adapter_uses_new_renderer_module_identity() -> None:
    source = Path("universal_runtime_v5_loader.py").read_text(encoding="utf-8")
    assert 'return _import("nfl_game_totals_page1_s_tier_v2")' in source
    assert '"nfl_game_totals_page1_s_tier_v2"' in source


def test_v2_renderer_module_exists() -> None:
    assert importlib.util.find_spec("nfl_game_totals_page1_s_tier_v2") is not None


def test_old_v1_identity_is_not_the_active_game_total_source_version() -> None:
    source = Path("universal_runtime_v5_loader.py").read_text(encoding="utf-8")
    block = source.split("def _nfl_game_total_adapter", 1)[1].split("def _nfl_passing_yards_adapter", 1)[0]
    assert '"nfl_game_totals_page1_s_tier_v1"' not in block
