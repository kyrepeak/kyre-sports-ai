from __future__ import annotations

import inspect
from pathlib import Path

import cfb_game_total_clean_page_v23 as page
import streamlit_memory_lazy_router_v168 as router


ROOT = Path(__file__).resolve().parents[1]


def _identity():
    return {
        "away": {
            "team": "Purdue",
            "conference": "Big Ten",
            "logo": "https://example.com/purdue.png",
        },
        "home": {
            "team": "UCLA",
            "conference": "Big Ten",
            "logo": "https://example.com/ucla.png",
        },
    }


def _stats(team: str, diff: float):
    return {
        "team": team,
        "record": "2-0",
        "ppg": 40.0 if team == "Purdue" else 36.5,
        "allowed_pg": 28.5 if team == "Purdue" else 17.0,
        "point_diff_pg": diff,
        "recent_form": "WW",
        "sample_games": 2,
        "quality": "GREEN",
        "source": "Certified Runtime Snapshot V2",
    }


def test_step4_ready_cards_show_identity_four_tiles_and_source():
    html = page._team_evidence_html_v23(
        _identity(),
        _stats("Purdue", 11.5),
        _stats("UCLA", 19.5),
    )
    assert "gt204-team-evidence" in html
    assert "Purdue" in html
    assert "UCLA" in html
    assert "purdue.png" in html
    assert "ucla.png" in html
    assert html.count('data-state="READY"') >= 10
    for key in ("ppg", "allowed", "point-diff", "recent-form"):
        assert f'data-stat="{key}"' in html
    for value in ("40.0", "28.5", "11.5", "36.5", "17.0", "19.5"):
        assert value in html
    assert html.count("WW") == 2
    assert "2 completed games" in html
    assert "Certified Runtime Snapshot V2" in html
    assert ">—<" not in html


def test_step4_pending_tiles_use_words_not_bare_dashes():
    pending = {
        "team": "Purdue",
        "record": "",
        "ppg": None,
        "allowed_pg": None,
        "point_diff_pg": None,
        "recent_form": "—",
        "sample_games": 0,
        "quality": "CHECK",
    }
    html = page._team_evidence_html_v23(
        _identity(),
        pending,
        pending | {"team": "UCLA"},
    )
    assert 'data-state="PENDING"' in html
    assert "Pending" in html
    assert "Record pending" in html
    assert "Sample pending" in html
    assert ">—<" not in html


def test_step4_diff_tiles_have_positive_and_negative_classes():
    positive = _stats("Purdue", 11.5)
    negative = _stats("UCLA", -3.5)
    html = page._team_evidence_html_v23(_identity(), positive, negative)
    assert 'gt204-stat diff positive' in html
    assert 'gt204-stat diff negative' in html


def test_step4_css_is_responsive_for_tablet_and_phone():
    css = page.STEP4_TEAM_EVIDENCE_CSS
    assert ".gt204-grid" in css
    assert "@media(max-width:850px)" in css
    assert "@media(max-width:620px)" in css
    assert "@media(max-width:420px)" in css
    assert "grid-template-columns:1fr" in css


def test_step4_temporarily_replaces_only_team_evidence_renderer():
    original = page.presentation_owner._target_team_evidence_html
    seen = {}

    def callback():
        seen["during"] = page.presentation_owner._target_team_evidence_html
        return "ok"

    assert page._render_with_step4_team_evidence_ui(callback) == "ok"
    assert seen["during"] is page._team_evidence_html_v23
    assert page.presentation_owner._target_team_evidence_html is original


def test_step4_preserves_step3_data_and_step6_certification():
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v22"
    assert "prior.render_step6_cert_surface" in inspect.getsource(
        page.render_step6_cert_surface
    )
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v23"
    assert "prior._render_step6_cert_surface" in inspect.getsource(
        router._render_step6_cert_surface
    )


def test_app_bootstrap_uses_v168_and_keeps_v167_compatibility_string():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_v168 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v167 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
