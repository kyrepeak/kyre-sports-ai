from __future__ import annotations

import inspect
from pathlib import Path

import cfb_game_total_clean_page_v24 as page
import cfb_game_total_game_evidence_v1 as owner
import streamlit_memory_lazy_router_v169 as router


ROOT = Path(__file__).resolve().parents[1]


def test_step5_overlay_repairs_only_missing_game_evidence(monkeypatch):
    monkeypatch.setattr(
        owner,
        "_environment_payload",
        lambda game: (
            {
                "event_id": "401858458",
                "kickoff": "2026-09-20T03:00Z",
                "status": "Scheduled",
                "venue": {
                    "ready": True,
                    "name": "Rose Bowl",
                    "city": "Pasadena",
                    "state": "CA",
                    "indoor": False,
                },
                "weather": {
                    "ready": True,
                    "temperature_f": 74.0,
                    "gust_mph": 9.0,
                    "precipitation_pct": 5.0,
                    "source": "certified weather",
                },
            },
            {"source": "test-environment"},
        ),
    )
    enriched, diag = owner.enrich_game_evidence(
        {
            "away_team": "Purdue",
            "home_team": "UCLA",
            "game_date": "2026-09-19",
        }
    )
    assert diag["data_green"] is True
    assert diag["fallback_used"] is True
    assert enriched["venue"] == "Rose Bowl"
    assert enriched["venue_location"] == "Pasadena, CA"
    assert enriched["temperature"] == 74.0
    assert enriched["wind"] == "9 mph gusts"
    assert enriched["weather"] == "5% precipitation"
    assert enriched["kickoff_iso"] == "2026-09-20T03:00Z"
    assert enriched["status"] == "Scheduled"
    assert enriched["game_evidence_event_id"] == "401858458"


def test_step5_does_not_fetch_when_required_evidence_is_already_good(monkeypatch):
    def fail(_game):
        raise AssertionError("environment fallback should not run")
    monkeypatch.setattr(owner, "_environment_payload", fail)
    existing = {
        "venue": "Rose Bowl",
        "venue_location": "Pasadena, CA",
        "temperature": 74,
        "weather": "Clear",
        "wind": "8 mph",
        "kickoff": "8:00 PM",
        "status": "Scheduled",
    }
    enriched, diag = owner.enrich_game_evidence(existing)
    assert diag["fallback_used"] is False
    assert diag["data_green"] is True
    for key, value in existing.items():
        assert enriched[key] == value


def test_step5_page_patches_only_v22_display_handoff_and_restores():
    original = page.handoff_owner._reconcile_display_bundle_v22
    seen = {}

    def callback():
        seen["during"] = page.handoff_owner._reconcile_display_bundle_v22
        return "ok"

    assert page._render_with_step5_game_evidence_data(callback) == "ok"
    assert seen["during"] is page._reconcile_display_bundle_v24
    assert page.handoff_owner._reconcile_display_bundle_v22 is original


def test_step5_preserves_step4_page_and_step6_certification():
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v23"
    assert "prior.render_step6_cert_surface" in inspect.getsource(
        page.render_step6_cert_surface
    )
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v24"
    assert "prior._render_step6_cert_surface" in inspect.getsource(
        router._render_step6_cert_surface
    )
    assert owner.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert owner.MAY_MODIFY_PROJECTION is False


def test_app_bootstrap_uses_v169_and_keeps_v168_compatibility_string():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_v169 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v168 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
