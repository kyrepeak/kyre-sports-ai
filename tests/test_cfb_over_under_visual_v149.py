"""V149 visual-only contract for the certified CFB Over/Under page."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v17 as page


def test_v149_converts_eastern_kickoff_to_phoenix_time():
    game = {
        "game_date": "2026-09-10",
        "kickoff_et": "8:00 PM ET",
    }
    assert page._phoenix_kickoff(game) == "5:00 PM MST"


def test_v149_quick_read_is_compact_and_keeps_sportsbook_weight_zero():
    html = page._quick_read({
        "analysis_line": 50.5,
        "raw": {
            "projected_total": 54.2,
            "structural_total_sigma": 8.1,
        },
        "final": {
            "selection": "OVER",
            "selection_probability": 0.62,
        },
    })
    for token in (
        "QUICK READ",
        "OVER",
        "54.2",
        "50.5",
        "+3.7",
        "62.0%",
        "0.0% SPORTSBOOK PROJECTION INFLUENCE",
    ):
        assert token in html


def test_v149_status_strip_covers_steps_5_through_10_without_changing_engines():
    html = page._status_strip({
        "explosive_engine": {"ready": True, "coverage": 1.0},
        "red_zone_engine": {"ready": True, "coverage": 1.0},
        "third_down_engine": {"ready": True, "coverage": 1.0},
        "turnover_engine": {"ready": True, "coverage": 1.0},
        "environment_engine": {"ready": True, "model_ready": False, "coverage": 0.0, "reason": "gated"},
        "history_engine": {"ready": True, "model_ready": False, "coverage": 0.4, "reason": "partial"},
    })
    for step in range(5, 11):
        assert f"STEP {step}" in html
    assert "GATED" in html
    assert "LIMITED" in html


def test_v149_deep_evidence_is_collapsed_by_default():
    source = inspect.getsource(page.render_over_under_hub)
    assert 'st.expander("Deep evidence • Steps 2–12", expanded=False)' in source


def test_v149_stays_visual_only_and_uses_existing_certified_runtime():
    source = inspect.getsource(page)
    assert "runtime_slate.analyze_game" in source
    assert "final_model.rank_slate" in source
    assert "sportsbook_api" not in source.lower()
    assert "monte_carlo(" not in source.lower()
