"""Regression tests for the real Step-1 exact ESPN logo wiring hotfix."""
from __future__ import annotations

from pathlib import Path

import cfb_over_under_clean_page_v17 as step1_owner
import cfb_over_under_clean_page_v37 as page
import cfb_over_under_logo_resolver_v2 as old_resolver
import cfb_over_under_logo_resolver_v3 as resolver
import streamlit_memory_lazy_router_v79 as router


def _game() -> dict:
    return {
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
        "away_espn_team_id": "2450",
        "home_espn_team_id": "258",
        "kickoff_et": "7:00 PM ET",
        "venue": "Scott Stadium",
        "broadcast": "ACCNX",
        "status": "Scheduled",
        "neutral_site": False,
    }


def _away() -> dict:
    return {
        "team": "Norfolk St.",
        "conference": "MEAC",
        "record_text": "1-1",
        "conference_record_text": "0-0",
        "head_coach": "Mike Vick",
        "division_context": "FCS",
        "ap_rank": None,
    }


def _home() -> dict:
    return {
        "team": "Virginia",
        "conference": "ACC",
        "record_text": "1-0",
        "conference_record_text": "1-0",
        "head_coach": "Tony Elliott",
        "division_context": "FBS",
        "ap_rank": 25,
    }


def test_v37_clones_the_real_v17_step1_with_exact_resolver():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v36"
    assert page.ACTIVE_LOGO_RESOLVER == "cfb_over_under_logo_resolver_v3"
    assert page._STEP1_EXACT.__code__ is step1_owner._step1.__code__
    assert page._STEP1_EXACT.__globals__["logo_resolver"] is resolver
    assert "EXACT ESPN TEAM-ID LOGOS WIRED TO STEP 1" in page._V37_MARKER


def test_real_step1_html_contains_exact_norfolk_state_and_virginia_logos(monkeypatch):
    def old_path_must_not_run(*args, **kwargs):
        raise AssertionError("old multi-source logo resolver must not run")

    monkeypatch.setattr(old_resolver, "resolve_visuals", old_path_must_not_run)

    html = page._STEP1_EXACT(_game(), _away(), _home())

    assert "https://a.espncdn.com/i/teamlogos/ncaa/500/2450.png" in html
    assert "https://a.espncdn.com/i/teamlogos/ncaa/500/258.png" in html
    assert ">NS<" not in html
    assert "Norfolk St." in html
    assert "Virginia" in html


def test_profiled_step1_uses_same_exact_renderer(monkeypatch):
    def old_path_must_not_run(*args, **kwargs):
        raise AssertionError("old multi-source logo resolver must not run")

    monkeypatch.setattr(old_resolver, "resolve_visuals", old_path_must_not_run)
    html = page._step1_v37(_game(), _away(), _home())
    assert "/2450.png" in html
    assert "/258.png" in html


def test_router_v79_advances_only_active_cfb_over_under_page():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v78"
    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v37"
    assert router.CFB_SPORT_LABEL == "College Football"
    assert router.OVER_UNDER_MARKET == "Over/Under"


def test_app_advances_to_v79_and_keeps_v77_v78_monster_contracts():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v77 import render_app as _frozen_v77_render_app" in text
    assert "from streamlit_memory_lazy_router_v78 import render_app as _frozen_v78_render_app" in text
    assert "from streamlit_memory_lazy_router_v77 import record_bootstrap_import_ms, render_app" in text
    assert "from streamlit_memory_lazy_router_v78 import record_bootstrap_import_ms, render_app" in text
    assert "from streamlit_memory_lazy_router_v79 import record_bootstrap_import_ms, render_app" in text
    assert "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11" in text
    assert "STREAMLIT_MAIN_V78_CFB_OU_EXACT_TEAM_LOGOS_2026-09-11" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V79_CFB_OU_EXACT_TEAM_LOGOS_WIRED_2026-09-11"'
        in text
    )
    assert "Monster Performance Diagnosis" in text
    assert "frozen V14 projection math" in text
    assert "0.0% sportsbook projection influence" in text
