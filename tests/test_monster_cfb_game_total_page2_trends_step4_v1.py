from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
STEP6 = ROOT / "cfb_game_total_page2_step6_trends_scoring_breakdown_v1.py"
STEP8 = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"


def _load_step6():
    spec = importlib.util.spec_from_file_location("monster_cfb_gt_page2_trends_step4", STEP6)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _profile(team: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "team": team,
        "completed_games": rows,
        "recent_ppg": None,
        "recent_points_allowed_pg": None,
    }


def test_step4_trends_use_verified_team_history_and_exclude_current_or_future_games() -> None:
    step6 = _load_step6()
    away = _profile(
        "Arizona State",
        [
            {"date": "2026-09-12", "points_for": 31, "points_against": 24},
            {"date": "2026-09-19", "points_for": 28, "points_against": 21},
            {"date": "2026-09-26", "points_for": 35, "points_against": 27},
            {"date": "2026-10-03", "points_for": 24, "points_against": 20},
            {"date": "2026-10-10", "points_for": 30, "points_against": 17},
            {"date": "2026-10-17", "points_for": 99, "points_against": 99},
        ],
    )
    home = _profile(
        "Texas Tech",
        [
            {"date": "2026-09-12", "points_for": 42, "points_against": 14},
            {"date": "2026-09-19", "points_for": 38, "points_against": 21},
            {"date": "2026-09-26", "points_for": 27, "points_against": 24},
            {"date": "2026-10-03", "points_for": 34, "points_against": 28},
            {"date": "2026-10-10", "points_for": 31, "points_against": 20},
            {"date": "2026-10-24", "points_for": 88, "points_against": 88},
        ],
    )

    html = step6.build_trends_scoring_breakdown_html(
        recent_totals=[],
        market_line=58.5,
        scoring_breakdown={},
        explosive_scoring=None,
        scoring_opportunities=None,
        red_zone_finishing=None,
        away_team="Arizona State",
        home_team="Texas Tech",
        away_profile=away,
        home_profile=home,
        as_of_day="2026-10-17",
    )

    assert "Arizona State" in html and "Texas Tech" in html
    for total in (55, 49, 62, 44, 47, 56, 59, 51, 62, 51):
        assert f">{total}<" in html
    assert ">198<" not in html
    assert ">176<" not in html
    assert "Recent scoring" in html
    assert "Recent allowed" in html
    assert "Scoring environment" in html


def test_step4_missing_verified_splits_show_one_truthful_empty_state_not_fake_numbers() -> None:
    step6 = _load_step6()
    html = step6.build_trends_scoring_breakdown_html(
        recent_totals=[],
        market_line=58.5,
        scoring_breakdown={},
        explosive_scoring=None,
        scoring_opportunities=None,
        red_zone_finishing=None,
        away_team="Arizona State",
        home_team="Texas Tech",
        away_profile={},
        home_profile={},
        as_of_day="2026-10-17",
    )
    assert "No verified half/quarter scoring splits available" in html
    assert "0.0" not in html
    assert "mock" not in html.lower()


def test_step4_runtime_binds_existing_away_home_profiles_into_stage3_without_provider_changes() -> None:
    source = STEP8.read_text(encoding="utf-8")
    assert "away_profile=away" in source
    assert "home_profile=home" in source
    assert "away_team=away_name" in source
    assert "home_team=home_name" in source
    assert "as_of_day=" in source
    lowered = source.lower()
    assert "requests." not in lowered
    assert "httpx." not in lowered


def test_step4_preserves_display_only_model_and_market_guards() -> None:
    step6 = _load_step6()
    assert step6.MAY_MODIFY_PAGE1 is False
    assert step6.MAY_MODIFY_PROJECTION is False
    assert step6.MAY_MODIFY_PROBABILITY is False
    assert step6.MAY_MODIFY_MODEL is False
    assert step6.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step6.NETWORK_CALLS_ADDED == 0
    assert step6.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
