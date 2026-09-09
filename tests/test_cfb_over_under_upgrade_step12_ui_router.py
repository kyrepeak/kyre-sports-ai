"""Regression checks for CFB O/U Upgrade Step 12 UI and Router V52."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v12 as ui
import streamlit_memory_lazy_router_v52 as router


def test_hero_preserves_step11_and_adds_final_strip(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP11_HERO", lambda *a, **k: "<STEP11/>")
    html = ui._hero_v12({}, {}, {})
    assert "<STEP11/>" in html
    assert "UPGRADE STEP 12" in html
    assert "0% NEW PROJECTION WEIGHT" in html


def test_cert_panel_certified():
    html = ui._cert_panel({
        "upgrade_step12_certification": {
            "status": "CERTIFIED",
            "checks_passed": 17,
            "checks_failed": 0,
            "checks_skipped": 0,
            "projection_fingerprint": "abc123",
            "integrity_passed": True,
            "blocking_failures": [],
        }
    })
    assert "CERTIFIED" in html
    assert "12/12 upgrade stack checked" in html
    assert "abc123" in html
    assert "checks failed" in html.lower()


def test_cert_panel_integrity_failure_names_blocker():
    html = ui._cert_panel({
        "upgrade_step12_certification": {
            "status": "INTEGRITY_FAIL",
            "checks_passed": 10,
            "checks_failed": 1,
            "checks_skipped": 0,
            "projection_fingerprint": "xyz",
            "blocking_failures": [{"name": "probability mass equals 1"}],
        }
    })
    assert "INTEGRITY FAIL" in html
    assert "probability mass equals 1" in html


def test_model_card_preserves_step11_and_adds_certificate(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP11_MODEL_CARD", lambda *a, **k: "<STEP11MODEL/>")
    output = {
        "upgrade_step12_certification": {
            "status": "CERTIFIED", "checks_passed": 5, "checks_failed": 0,
            "checks_skipped": 0, "projection_fingerprint": "fp",
            "blocking_failures": [],
        }
    }
    html = ui._model_card_v12({}, {}, {}, output)
    assert "<STEP11MODEL/>" in html
    assert "FINAL SYSTEM CERTIFICATION" in html


def test_router_v52_only_advances_cfb_ou(monkeypatch):
    seen = {}
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    module = types.SimpleNamespace(render_cfb_hub=lambda market, *args: seen.update({"market": market}))
    monkeypatch.setattr(router.root, "_import", lambda name: (seen.update({"module": name}) or module))
    router._render_nfl_or_cfb_v52("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v12"
    assert seen["market"] == "Over/Under"


def test_router_delegates_other_routes(monkeypatch):
    seen = []
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda m: seen.append(m))
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    router._render_nfl_or_cfb_v52("Moneyline")
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v52("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v51_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v51
    seen = {}
    monkeypatch.setattr(router.prior, "render_app", lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v51}))
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v52
    assert router.prior._render_nfl_or_cfb_v51 is original
