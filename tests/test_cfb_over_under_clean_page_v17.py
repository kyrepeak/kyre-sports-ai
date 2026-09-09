"""Regression tests for the direct Clean Page V17."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v17 as page
import cfb_over_under_runtime_team_data_v1 as runtime


def _game():
    return {
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
        "kickoff_et": "8:00 PM ET",
        "venue": "Hard Rock Stadium",
        "broadcast": "ACC Network",
        "status": "Scheduled",
        "neutral_site": False,
    }


def _profiles():
    away = {
        "team": "Florida A&M",
        "conference": "SWAC",
        "division_context": "FCS",
        "record_text": "1-1",
        "conference_record_text": "0-0",
        "home_record": {"wins": 1, "losses": 0, "ties": 0, "games": 1},
        "away_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
        "recent_form": "WL",
        "head_coach": "Quinn Gray Sr.",
        "polls": {},
        "official_stats": {},
    }
    home = {
        "team": "Miami (FL)",
        "conference": "ACC",
        "division_context": "FBS",
        "record_text": "1-0",
        "conference_record_text": "1-0",
        "home_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
        "away_record": {"wins": 1, "losses": 0, "ties": 0, "games": 1},
        "recent_form": "W",
        "head_coach": "Mario Cristobal",
        "ap_rank": 7,
        "coaches_poll_rank": 7,
        "polls": {
            "ap": {"rank": 7},
            "coaches": {"rank": 7},
        },
        "official_stats": {},
    }
    return away, home


def test_runtime_alias_makes_miami_fl_match_espn_miami():
    assert runtime._key("Miami (FL)") == runtime._key("Miami")
    assert runtime._key("Miami (OH)") == runtime._key("Miami")


def test_new_step1_renders_current_runtime_data(monkeypatch):
    away, home = _profiles()
    monkeypatch.setattr(
        page.logo_resolver,
        "resolve_visuals",
        lambda game: {"away": {}, "home": {}},
    )
    html = page._step1(_game(), away, home)
    for token in (
        "STEP 1",
        "NEW RENDERER",
        "Florida A&amp;M",
        "Miami (FL)",
        "1-1 overall",
        "1-0 overall",
        "Hard Rock Stadium",
        "ACC Network",
        "Quinn Gray Sr.",
        "Mario Cristobal",
        "#7 AP",
    ):
        assert token in html
    assert "Venue unavailable" not in html
    assert "Broadcast unavailable" not in html


def test_new_step2_renders_current_poll_and_split_data():
    away, home = _profiles()
    html = page._step2(away, home)
    assert "NO LEGACY STEP-2 ENGINE" in html
    assert "1-1" in html
    assert "1-0" in html
    assert "WL" in html
    assert ">W<" in html
    assert html.count("#7") >= 2
    assert "Mario Cristobal" in html
    assert "Quinn Gray Sr." in html
    assert "N/A" in html


def test_clean_page_does_not_import_legacy_step1_or_step2_ui():
    source = inspect.getsource(page)
    assert "cfb_over_under_matchup_ui_v1" not in source
    assert "cfb_over_under_matchup_ui_v2" not in source
    assert "cfb_over_under_matchup_ui_v15" not in source
    assert "cfb_over_under_matchup_ui_v16" not in source


def test_engine_status_requires_model_ready_not_generic_ready():
    assert page._engine_ready({
        "ready": True,
        "model_ready": False,
        "coverage": 0.0,
        "reason": "missing verified event",
    }) == "GATED"

    assert page._engine_ready({
        "ready": True,
        "model_ready": False,
        "coverage": 0.45,
        "reason": "partial evidence",
    }) == "LIMITED"

    assert page._engine_ready({
        "ready": True,
        "model_ready": True,
        "coverage": 1.0,
    }) == "READY"


def test_engine_status_preserves_legacy_ready_for_engines_without_model_ready():
    assert page._engine_ready({"ready": True, "coverage": 1.0}) == "READY"


def test_gated_step_discloses_zero_new_model_influence():
    html = page._model_step(
        9,
        "GAME-DAY ENVIRONMENT",
        {
            "ready": True,
            "model_ready": False,
            "coverage": 0.0,
            "reason": "exact same-date ESPN event identity is unavailable",
        },
    )
    assert ">GATED<" in html
    assert "0% new model influence" in html
    assert ">READY<" not in html
