from __future__ import annotations

import inspect
from pathlib import Path

import cfb_game_total_clean_page_v4 as stats_owner
import cfb_game_total_clean_page_v22 as page
import cfb_game_total_team_evidence_data_v1 as data_owner
import streamlit_memory_lazy_router_v167 as router


ROOT = Path(__file__).resolve().parents[1]


def _step1_profile(team: str):
    return {
        "team": team,
        "record": {"wins": 2, "losses": 0, "ties": 0, "games": 2},
        "record_text": "2-0",
        "completed_games": [
            {
                "event_id": "a",
                "date": "2026-09-05",
                "location": "home",
                "points_for": 42,
                "points_against": 21,
                "result": "W",
            },
            {
                "event_id": "b",
                "date": "2026-09-12",
                "location": "away",
                "points_for": 38,
                "points_against": 36,
                "result": "W",
            },
        ],
        "ppg": 40.0,
        "points_allowed_pg": 28.5,
        "point_diff_pg": 11.5,
        "recent_form": "WW",
        "data_source": "Certified Runtime Snapshot V2",
    }


def test_step3_repairs_nonempty_but_scoring_incomplete_display_profile():
    display = {
        "team": "Purdue",
        "espn_team_id": "2509",
        "record_text": "2-0",
        "official_stats": {"some": {"value": "kept"}},
    }
    repaired, used = data_owner.repair_team_evidence_profile(
        display, _step1_profile("Purdue")
    )
    assert used is True
    assert repaired["espn_team_id"] == "2509"
    assert repaired["official_stats"] == {"some": {"value": "kept"}}
    assert len(repaired["completed_games"]) == 2
    stats = stats_owner._team_stats_state(
        repaired,
        {"away_team": "Purdue"},
        "away",
    )
    assert stats["quality"] == "GREEN"
    assert stats["sample_games"] == 2
    assert stats["ppg"] == 40.0
    assert stats["allowed_pg"] == 28.5
    assert stats["point_diff_pg"] == 11.5
    assert stats["recent_form"] == "WW"


def test_step3_does_not_replace_existing_usable_display_sample():
    display = {
        "team": "Purdue",
        "completed_games": [
            {
                "event_id": "display",
                "date": "2026-09-12",
                "location": "home",
                "points_for": 30,
                "points_against": 20,
            }
        ],
        "data_source": "already-good-display",
    }
    repaired, used = data_owner.repair_team_evidence_profile(
        display, _step1_profile("Purdue")
    )
    assert used is False
    assert repaired == display


def test_step3_bundle_reports_data_green_for_both_sides():
    away, home, diag = data_owner.repair_team_evidence_bundle(
        {"team": "Purdue"},
        {"team": "UCLA"},
        _step1_profile("Purdue"),
        _step1_profile("UCLA"),
    )
    assert diag["data_green"] is True
    assert diag["repaired_sides"] == ["away", "home"]
    assert data_owner.has_team_evidence_sample(away)
    assert data_owner.has_team_evidence_sample(home)


def test_step3_page_patches_only_v164_display_handoff_and_restores_it():
    original = page.handoff_owner._reconcile_display_bundle_v164
    seen = {}

    def callback():
        seen["during"] = page.handoff_owner._reconcile_display_bundle_v164
        return "ok"

    assert page._render_with_step3_team_evidence_data(callback) == "ok"
    assert seen["during"] is page._reconcile_display_bundle_v22
    assert page.handoff_owner._reconcile_display_bundle_v164 is original


def test_step3_preserves_step2_page_and_step6_certification():
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v21"
    assert "prior.render_step6_cert_surface" in inspect.getsource(
        page.render_step6_cert_surface
    )
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v22"
    assert "prior._render_step6_cert_surface" in inspect.getsource(
        router._render_step6_cert_surface
    )


def test_app_bootstrap_uses_v167_and_keeps_v166_compatibility_string():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_v167 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v166 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
