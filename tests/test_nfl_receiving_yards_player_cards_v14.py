from __future__ import annotations

from pathlib import Path


def _helper():
    import nfl_receiving_yards_presentation_v1 as helper

    return helper


def test_toughness_normalization_is_finite_and_neutral_by_default() -> None:
    helper = _helper()
    assert helper.normalize_toughness("FAVORABLE") == "FAVORABLE"
    assert helper.normalize_toughness("medium") == "MEDIUM"
    assert helper.normalize_toughness("TOUGH") == "TOUGH"
    assert helper.normalize_toughness("unknown") == "MEDIUM"
    assert helper.normalize_toughness(None) == "MEDIUM"


def test_semantic_role_reuses_toughness_without_new_scoring() -> None:
    helper = _helper()
    assert helper.semantic_role("FAVORABLE") == "favorable"
    assert helper.semantic_role("MEDIUM") == "medium"
    assert helper.semantic_role("TOUGH") == "tough"


def test_v14_reuses_frozen_v10_toughness_and_only_changes_presentation() -> None:
    source = Path("nfl_receiving_yards_hub_v14.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v13"' in source
    assert 'FROZEN_DETAILED_CARD = "nfl_receiving_yards_hub_v10"' in source
    assert "detailed_page._grade_for_team_opponent" in source
    assert "FAVORABLE_THRESHOLDS" not in source
    assert "TOUGH_THRESHOLDS" not in source
    assert "MATCHUP TOUGHNESS" in source
    assert "DEEP EVIDENCE" in source
    assert "Quick Read" in source
    assert "krecv14-model" in source
    assert "krecv14-info" in source
    assert "krecv14-tier" in source
    assert "krecv6-wrap" in source
    assert "krecv7-wrap" in source
    assert "DISPLAY_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_router_v145_advances_only_receiving_yards() -> None:
    source = Path("streamlit_memory_lazy_router_v145.py").read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v144"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v14"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_bootstraps_router_v145() -> None:
    source = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v145 import record_bootstrap_import_ms, render_app" in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V145_NFL_RECEIVING_YARDS_PLAYER_CARD_REDESIGN_2026-09-16"' in source
