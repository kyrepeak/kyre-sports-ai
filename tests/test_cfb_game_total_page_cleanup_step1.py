from __future__ import annotations

import inspect
from pathlib import Path

import cfb_game_total_clean_page_v20 as page_v20
import cfb_game_total_model_input_v1 as model_input
import cfb_game_total_slate_v1 as slate_v1
import cfb_game_total_slate_v2 as slate_v2
import streamlit_memory_lazy_router_v165 as router_v165


ROOT = Path(__file__).resolve().parents[1]


def _runtime_payload():
    return {
        "_runtime_snapshot_source": "certified-runtime-branch",
        "generated_at": "2026-09-19T23:03:44Z",
        "window": {"start": "2026-09-18", "end": "2026-09-25"},
        "games": [
            {
                "event_id": "401858458",
                "game_date": "2026-09-19",
                "away_team": "Purdue",
                "home_team": "UCLA",
                "away": {
                    "team_id": "2509",
                    "team": "Purdue",
                    "completed_games": [
                        {
                            "event_id": "p1",
                            "date": "2026-09-05",
                            "opponent": "A",
                            "opponent_id": "1",
                            "location": "home",
                            "points_for": 42,
                            "points_against": 21,
                        },
                        {
                            "event_id": "p2",
                            "date": "2026-09-12",
                            "opponent": "B",
                            "opponent_id": "2",
                            "location": "away",
                            "points_for": 38,
                            "points_against": 36,
                        },
                    ],
                },
                "home": {
                    "team_id": "26",
                    "team": "UCLA",
                    "completed_games": [
                        {
                            "event_id": "u1",
                            "date": "2026-09-05",
                            "opponent": "C",
                            "opponent_id": "3",
                            "location": "home",
                            "points_for": 35,
                            "points_against": 14,
                        },
                        {
                            "event_id": "u2",
                            "date": "2026-09-12",
                            "opponent": "D",
                            "opponent_id": "4",
                            "location": "away",
                            "points_for": 38,
                            "points_against": 20,
                        },
                    ],
                },
            }
        ],
    }


def test_model_input_repairs_only_incomplete_exact_event_profiles(monkeypatch):
    monkeypatch.setattr(
        model_input.runtime_owner.runtime_snapshot_v2,
        "_load_v2_snapshot",
        lambda: _runtime_payload(),
    )
    game = {
        "event_id": "401858458",
        "game_date": "2026-09-19",
        "away_team": "Purdue",
        "home_team": "UCLA",
    }
    empty = {
        "away": {
            "team": "Purdue",
            "record": {"games": 0},
            "ppg": None,
            "points_allowed_pg": None,
            "data_quality": {"grade": "CHECK"},
        },
        "home": {
            "team": "UCLA",
            "record": {"games": 0},
            "ppg": None,
            "points_allowed_pg": None,
            "data_quality": {"grade": "CHECK"},
        },
    }
    repaired, diag = model_input.enrich_matchup_model_profiles(
        game, "2026-09-19", empty
    )

    assert diag["fallback_used"] is True
    assert diag["event_id"] == "401858458"
    assert diag["repaired_sides"] == ["away", "home"]

    purdue = repaired["away"]
    ucla = repaired["home"]
    assert purdue["record"]["games"] == 2
    assert purdue["ppg"] == 40.0
    assert purdue["points_allowed_pg"] == 28.5
    assert purdue["point_diff_pg"] == 11.5
    assert purdue["recent_form"] == "WW"
    assert purdue["data_quality"]["grade"] != "CHECK"

    assert ucla["record"]["games"] == 2
    assert ucla["ppg"] == 36.5
    assert ucla["points_allowed_pg"] == 17.0
    assert ucla["point_diff_pg"] == 19.5
    assert ucla["recent_form"] == "WW"
    assert ucla["data_quality"]["grade"] != "CHECK"


def test_model_input_preserves_existing_model_ready_profiles(monkeypatch):
    def should_not_fetch():
        raise AssertionError("Runtime fallback must not run for ready profiles")

    monkeypatch.setattr(
        model_input.runtime_owner.runtime_snapshot_v2,
        "_load_v2_snapshot",
        should_not_fetch,
    )
    profiles = {
        "away": {
            "team": "Away",
            "record": {"games": 3},
            "ppg": 30.0,
            "points_allowed_pg": 20.0,
            "data_quality": {"grade": "LIMITED"},
        },
        "home": {
            "team": "Home",
            "record": {"games": 3},
            "ppg": 28.0,
            "points_allowed_pg": 21.0,
            "data_quality": {"grade": "READY"},
        },
    }
    out, diag = model_input.enrich_matchup_model_profiles(
        {"event_id": "x"}, "2026-09-19", profiles
    )
    assert diag["fallback_used"] is False
    assert out == profiles


def test_slate_v2_uses_exact_frozen_math_owners():
    assert slate_v2.raw_model is slate_v1.raw_model
    assert slate_v2.final_model is slate_v1.final_model
    assert slate_v2.team_data is slate_v1.team_data
    assert slate_v2.model_input.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert slate_v2.model_input.MAY_MODIFY_PROJECTION is False


def test_page_v20_temporarily_swaps_slate_and_truthful_hero():
    original_slate = page_v20.compact_owner.frozen_page.slate
    original_hero = page_v20.compact_owner._game_total_hero_html
    seen = {}

    def callback():
        seen["slate"] = page_v20.compact_owner.frozen_page.slate
        seen["hero"] = page_v20.compact_owner._game_total_hero_html
        return "ok"

    assert page_v20._render_with_v20_slate(callback) == "ok"
    assert seen["slate"] is slate_v2
    assert seen["hero"] is page_v20._game_total_hero_html_v20
    assert page_v20.compact_owner.frozen_page.slate is original_slate
    assert page_v20.compact_owner._game_total_hero_html is original_hero


def test_step6_certification_stays_on_v19():
    source = inspect.getsource(page_v20.render_step6_cert_surface)
    assert "prior.render_step6_cert_surface" in source
    router_source = inspect.getsource(router_v165._render_step6_cert_surface)
    assert "prior._render_step6_cert_surface" in router_source
    assert "cfb_game_total_clean_page_v20" not in router_source


def test_router_v165_activates_v20_only_for_normal_game_total():
    assert router_v165.ACTIVE_PAGE == "cfb_game_total_clean_page_v20"
    assert router_v165.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router_v165.MAY_MODIFY_PROJECTION is False
    source = inspect.getsource(router_v165.render_app)
    assert "_step6_cert_requested" in source
    assert "_render_step6_cert_surface" in source
    assert "_render_exact_game_total_surface" in source


def test_app_bootstrap_uses_v165_and_keeps_frozen_compatibility_strings():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_v165 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v164 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v163 import "
        "record_bootstrap_import_ms, render_app"
    ) in source


def test_page_v20_hero_reports_ready_not_missing_count():
    html = page_v20._game_total_hero_html_v20(
        raw={},
        final={},
        display_game={"market_total": 52.5},
        statuses={},
        ready_count=3,
    )
    assert "3/12 Data Check" in html
    assert "9 required checks pending" in html
    assert "Projection unavailable" in html
    assert "Market verified • model projection pending" in html
    assert "Market total unavailable" not in html
