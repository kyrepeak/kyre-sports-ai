"""Regression tests for exact ESPN team-ID-only CFB O/U logos."""
from __future__ import annotations

import json
from pathlib import Path

import cfb_over_under_clean_page_v36 as page
import cfb_over_under_logo_resolver_v3 as resolver
import streamlit_memory_lazy_router_v78 as router


def test_known_verified_matchup_uses_exact_espn_team_ids():
    visuals = resolver.resolve_visuals(
        {
            "away_team": "Norfolk State",
            "home_team": "Virginia",
            "away_espn_team_id": "2450",
            "home_espn_team_id": "258",
        }
    )

    assert visuals["away"]["team_id"] == "2450"
    assert visuals["away"]["logo"] == "https://a.espncdn.com/i/teamlogos/ncaa/500/2450.png"
    assert visuals["home"]["team_id"] == "258"
    assert visuals["home"]["logo"] == "https://a.espncdn.com/i/teamlogos/ncaa/500/258.png"
    assert visuals["away"]["exact_identity"] is True
    assert visuals["home"]["exact_identity"] is True


def test_runtime_snapshot_team_ids_are_used_without_name_guessing():
    payload = json.loads(Path("data/cfb_runtime_snapshot_v2.json").read_text(encoding="utf-8"))
    games = payload.get("games") or []
    assert games

    for game in games:
        visuals = resolver.resolve_visuals(game)
        for side in ("away", "home"):
            expected = str((game.get(side) or {}).get("team_id") or "").strip()
            assert expected.isdigit()
            assert visuals[side]["team_id"] == expected
            assert visuals[side]["logo"] == resolver.ESPN_LOGO_CDN_TEMPLATE.format(team_id=expected)
            assert visuals[side]["logo_provider"] == "espn_exact_team_id"
            assert visuals[side]["confidence"] == "HIGH"


def test_missing_or_unsafe_team_id_fails_closed_instead_of_guessing():
    visuals = resolver.resolve_visuals(
        {
            "away_team": "Example State",
            "home_team": "Example Tech",
            "away_espn_team_id": "not-a-number",
            "home_espn_team_id": "",
        }
    )

    assert visuals["away"]["logo"] == ""
    assert visuals["home"]["logo"] == ""
    assert visuals["away"]["exact_identity"] is False
    assert visuals["home"]["exact_identity"] is False
    assert resolver.NETWORK_LOOKUPS_ENABLED is False
    assert resolver.FUZZY_LOGO_MATCHING is False
    assert resolver.NAME_BASED_LOGO_MATCHING is False


def test_v36_step1_is_cloned_with_exact_logo_resolver_only():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v35"
    assert page.ACTIVE_LOGO_RESOLVER == "cfb_over_under_logo_resolver_v3"
    assert page._STEP1_V36.__globals__["logo_resolver"] is resolver
    marker = page._V36_MARKER
    assert "EXACT ESPN TEAM-ID LOGOS ACTIVE" in marker
    assert "NO NAME-BASED LOGO MATCHING" in marker
    assert "NO WIKIPEDIA/WIKIMEDIA LOGO GUESSING" in marker
    assert "0.0% SPORTSBOOK PROJECTION INFLUENCE" in marker
    assert "FROZEN V14 PROJECTION MATH PRESERVED" in marker


def test_router_v78_advances_only_active_cfb_over_under_page():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v77"
    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v36"
    assert router.CFB_SPORT_LABEL == "College Football"
    assert router.OVER_UNDER_MARKET == "Over/Under"


def test_app_advances_to_v78_and_preserves_monster_instrumentation():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v77 import render_app as _frozen_v77_render_app" in text
    assert "from streamlit_memory_lazy_router_v78 import record_bootstrap_import_ms, render_app" in text
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V78_CFB_OU_EXACT_TEAM_LOGOS_2026-09-11"' in text
    assert "Monster Performance Diagnosis" in text
    assert "frozen V14 projection math" in text
    assert "0.0% sportsbook projection influence" in text
