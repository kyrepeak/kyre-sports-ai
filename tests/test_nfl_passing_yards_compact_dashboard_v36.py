from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V36 = ROOT / "nfl_passing_yards_hub_v36.py"


def _v36_source() -> str:
    assert V36.exists(), "Step 4 RED: nfl_passing_yards_hub_v36.py has not been built yet"
    return V36.read_text(encoding="utf-8")


def test_v36_compact_dashboard_is_additive_and_freeze_safe() -> None:
    source = _v36_source()

    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v35"' in source
    assert 'FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "COMPACT_DASHBOARD_ONLY = True" in source
    assert "import nfl_passing_yards_hub_v35 as prior" in source


def test_v36_compact_dashboard_shell_has_stable_ui_hooks() -> None:
    source = _v36_source()

    for hook in (
        "monster-pass-dashboard",
        "monster-matchup-header",
        "monster-qb-hero-grid",
        "monster-why-projection",
        "monster-deep-evidence",
    ):
        assert hook in source

    assert "@media" in source
    assert "render_nfl_passing_yards_hub" in source
    assert "render_nfl_hub" in source
