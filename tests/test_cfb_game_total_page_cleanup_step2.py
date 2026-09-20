from __future__ import annotations

import inspect
from pathlib import Path

import cfb_game_total_clean_page_v21 as page
import streamlit_memory_lazy_router_v166 as router


ROOT = Path(__file__).resolve().parents[1]


def test_step2_ready_hero_renders_four_explicit_ready_cards():
    html = page._game_total_hero_html_v21(
        raw={"projected_combined_total": 55.5},
        final={
            "ready": True,
            "projected_combined_total": 55.5,
            "forecast_strength": 0.72,
            "grade": "A",
        },
        display_game={"market_total": 52.5},
        statuses={},
        ready_count=12,
    )
    assert "GAME TOTAL ANALYSIS" in html
    assert 'data-metric="projected-total" data-state="READY"' in html
    assert 'data-metric="market-total" data-state="READY"' in html
    assert 'data-metric="lean" data-state="READY"' in html
    assert 'data-metric="confidence" data-state="READY"' in html
    assert ">55.5<" in html
    assert ">52.5<" in html
    assert "Over +3.0" in html
    assert "72.0%" in html
    assert "Grade: A" in html
    assert "12/12 Data Check" in html
    assert "All 12 required checks ready" in html
    assert "sportsbook projection influence" in html.lower()


def test_step2_pending_states_use_words_not_bare_dashes():
    html = page._game_total_hero_html_v21(
        raw={},
        final={},
        display_game={"market_total": 52.5},
        statuses={},
        ready_count=10,
    )
    assert 'data-metric="projected-total" data-state="PENDING"' in html
    assert 'data-metric="market-total" data-state="READY"' in html
    assert 'data-metric="lean" data-state="PENDING"' in html
    assert 'data-metric="confidence" data-state="PENDING"' in html
    assert "Pending" in html
    assert "Waiting on projection" in html
    assert "Market verified • model projection pending" in html
    assert "10/12 Data Check" in html
    assert "2 required checks pending" in html
    assert ">—<" not in html


def test_step2_missing_market_is_explicit_not_blank():
    html = page._game_total_hero_html_v21(
        raw={"projected_combined_total": 55.5},
        final={
            "ready": True,
            "projected_combined_total": 55.5,
            "forecast_strength": 0.64,
            "grade": "B",
        },
        display_game={},
        statuses={},
        ready_count=11,
    )
    assert "Not posted" in html
    assert "Waiting on market" in html
    assert "Model ready • no verified market line posted" in html
    assert ">—<" not in html


def test_step2_css_is_scoped_and_responsive():
    css = page.STEP2_PRESENTATION_CSS
    assert ".gt202-totalgrid" in css
    assert "@media (max-width:900px)" in css
    assert "@media (max-width:600px)" in css
    assert "grid-template-columns:repeat(2" in css
    assert "grid-template-columns:1fr" in css


def test_step2_page_temporarily_replaces_only_v20_hero():
    original = page.prior._game_total_hero_html_v20
    seen = {}

    def callback():
        seen["during"] = page.prior._game_total_hero_html_v20
        return "ok"

    assert page._render_with_v21_presentation(callback) == "ok"
    assert seen["during"] is page._game_total_hero_html_v21
    assert page.prior._game_total_hero_html_v20 is original


def test_step2_preserves_step1_data_and_step6_cert_routes():
    assert page.prior.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v19"
    step6_source = inspect.getsource(page.render_step6_cert_surface)
    assert "prior.render_step6_cert_surface" in step6_source
    router_source = inspect.getsource(router._render_step6_cert_surface)
    assert "prior._render_step6_cert_surface" in router_source
    assert "cfb_game_total_clean_page_v21" not in router_source


def test_step2_router_activates_v21_for_normal_route_only():
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v21"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_app_bootstrap_uses_v166_and_retains_v165_compatibility_string():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_v166 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v165 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
