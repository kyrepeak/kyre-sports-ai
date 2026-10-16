from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step5_team_snapshot_key_drivers_v1.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("monster_cfb_gt_page2_team_snapshot_step3", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step3_missing_team_snapshot_values_keep_fail_soft_dash_and_explain_unverified_state() -> None:
    step5 = _load_module()
    html = step5.build_team_snapshot_key_drivers_html(
        away_team="Arizona State",
        home_team="Texas Tech",
        away_pace=None,
        home_pace=None,
        away_explosive=None,
        home_explosive=None,
        away_red_zone=None,
        home_red_zone=None,
        away_defense=None,
        home_defense=None,
        favorable_for={},
    )

    # Keep the frozen fail-soft placeholder, but never leave it unexplained.
    assert html.count("—") >= 8
    for message in (
        "No verified pace available",
        "No verified explosive-play data available",
        "No verified red-zone rate available",
        "No verified defensive snapshot available",
    ):
        assert message in html

    assert html.count('data-availability="missing"') == 8
    assert 'data-driver="pace"' in html
    assert 'data-driver="explosive"' in html
    assert 'data-driver="red_zone"' in html
    assert 'data-driver="defense"' in html

    # The repair is explanatory only; it must not manufacture a favorable side.
    assert "Favorable: Arizona State" not in html
    assert "Favorable: Texas Tech" not in html
