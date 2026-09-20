from __future__ import annotations

import inspect

from devsystem import production_verify_page_cleanup_step6 as verifier


def test_step6_verifier_targets_exact_cleanup_contract():
    assert verifier.CERT_DATE == "2026-09-19"
    assert verifier.CERT_EVENT_ID == "401858458"
    assert verifier.CERT_MATCHUP == "Purdue @ UCLA"
    assert "STEP2_PRESENTATION_ACTIVE" in verifier.STEP2_MARKER
    assert "STEP4_TEAM_EVIDENCE_UI_ACTIVE" in verifier.STEP4_MARKER


def test_step6_verifier_is_passive_stable_session():
    source = inspect.getsource(verifier.verify)
    waiter = inspect.getsource(verifier._wait_for_cleanup_surface)
    combined = source + waiter
    assert "page.reload" not in combined
    assert "reload(" not in combined
    assert "restart" not in combined.lower()
    assert "clear_cache" not in combined
    assert '"/~/+/?"' in source
    assert "page.wait_for_timeout(2000)" in waiter


def test_step6_verifier_requires_all_cleanup_surfaces():
    hero = inspect.getsource(verifier._assert_hero)
    teams = inspect.getsource(verifier._assert_team_evidence)
    game = inspect.getsource(verifier._assert_game_evidence)
    assert "12/12 Data Check" in hero
    assert "ready_metrics.count() != 4" in hero
    assert "0.0% sportsbook projection influence" in hero
    assert "ready_cards.count() != 2" in teams
    assert "ready_stats.count() != 8" in teams
    assert "Rose Bowl" in game
    assert '"unavailable" in lowered' in game
    assert "Scheduled" in game


def test_step6_verifier_does_not_modify_projection_or_product():
    source = inspect.getsource(verifier)
    assert "sportsbook_projection_influence" in source
    assert '"projection_mutation": False' in source
    assert "streamlit_memory_lazy_router" not in source
    assert "cfb_game_total_clean_page" not in source
