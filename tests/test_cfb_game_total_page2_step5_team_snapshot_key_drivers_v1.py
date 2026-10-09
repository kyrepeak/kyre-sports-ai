from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step5_team_snapshot_key_drivers_v1.py"


def _load_module():
    assert MODULE.is_file(), "Page-2 Step-5 team-snapshot module must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step5", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step5_team_snapshot_component_exists_before_green() -> None:
    assert MODULE.is_file(), "Page-2 Step-5 team-snapshot module must exist before GREEN"


def test_step5_renders_team_comparison_and_all_key_drivers() -> None:
    step5 = _load_module()
    html = step5.build_team_snapshot_key_drivers_html(
        away_team="Texas",
        home_team="Oklahoma",
        away_pace="72.4 plays/game",
        home_pace="68.1 plays/game",
        away_explosive="8.7 plays/game",
        home_explosive="6.9 plays/game",
        away_red_zone="71.4%",
        home_red_zone="64.8%",
        away_defense="18.6 pts/game",
        home_defense="24.1 pts/game",
        favorable_for={
            "pace": "away",
            "explosive": "away",
            "red_zone": "away",
            "defense": "away",
        },
    )

    assert 'id="gtp2-team-snapshot"' in html
    assert 'data-testid="gtp2s5-team-snapshot"' in html
    assert "Team Snapshot + Key Drivers" in html
    assert "Texas" in html and "Oklahoma" in html
    assert "Pace" in html
    assert "Explosive Plays" in html
    assert "Red-Zone Rate" in html
    assert "Defense" in html
    assert "72.4 plays/game" in html and "68.1 plays/game" in html
    assert "8.7 plays/game" in html and "6.9 plays/game" in html
    assert "71.4%" in html and "64.8%" in html
    assert "18.6 pts/game" in html and "24.1 pts/game" in html
    assert html.count("Favorable") >= 4


def test_step5_favorable_side_is_display_only_and_explicit() -> None:
    step5 = _load_module()
    html = step5.build_team_snapshot_key_drivers_html(
        away_team="Away",
        home_team="Home",
        away_pace=71.0,
        home_pace=74.0,
        away_explosive=7.0,
        home_explosive=9.0,
        away_red_zone=0.70,
        home_red_zone=0.65,
        away_defense=20.0,
        home_defense=17.0,
        favorable_for={"pace": "home", "explosive": "home", "red_zone": "away", "defense": "home"},
    )

    assert 'data-driver="pace"' in html
    assert 'data-favorable="home"' in html
    assert 'data-driver="red_zone"' in html
    assert 'data-favorable="away"' in html
    assert "Favorable: Home" in html
    assert "Favorable: Away" in html


def test_step5_is_presentation_only_and_preserves_frozen_predecessors() -> None:
    step5 = _load_module()
    assert step5.STEP2_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
    assert step5.STEP3_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
    assert step5.STEP4_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
    assert step5.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_FROZEN"
    assert step5.MAY_MODIFY_PAGE1 is False
    assert step5.MAY_MODIFY_PROJECTION is False
    assert step5.MAY_MODIFY_PROBABILITY is False
    assert step5.MAY_MODIFY_MODEL is False
    assert step5.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step5.NETWORK_CALLS_ADDED == 0
    assert step5.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    source = MODULE.read_text(encoding="utf-8").lower()
    assert "requests." not in source
    assert "httpx." not in source
    assert "urllib.request" not in source


def test_step5_missing_values_fail_soft_without_data_limited_copy() -> None:
    step5 = _load_module()
    html = step5.build_team_snapshot_key_drivers_html(
        away_team=None,
        home_team=None,
        away_pace=None,
        home_pace=None,
        away_explosive=None,
        home_explosive=None,
        away_red_zone=None,
        home_red_zone=None,
        away_defense=None,
        home_defense=None,
        favorable_for=None,
    )

    assert html.count("—") >= 10
    assert "data limited" not in html.lower()
    assert "pending" not in html.lower()


def test_step5_escapes_text_and_is_mobile_responsive() -> None:
    step5 = _load_module()
    html = step5.build_team_snapshot_key_drivers_html(
        away_team='<script>alert("x")</script>',
        home_team="Home",
        away_pace="71",
        home_pace="72",
        away_explosive="7",
        home_explosive="8",
        away_red_zone="70%",
        home_red_zone="65%",
        away_defense="20",
        home_defense="21",
        favorable_for={},
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "@media(max-width:760px)" in html
    assert "@media(max-width:480px)" in html
