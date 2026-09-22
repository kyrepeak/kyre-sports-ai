from __future__ import annotations

import importlib


def test_v39_compact_step_state_does_not_claim_identity_missing_when_ids_are_verified() -> None:
    page = importlib.import_module("cfb_over_under_clean_page_v39")
    game = {"away_team": "Syracuse", "home_team": "Pittsburgh", "away_espn_id": "183", "home_espn_id": "221"}
    engine = {"status": "GATED", "reason": "NCAA FBS/FCS identity is unavailable for one or both teams."}

    state = page._compact_step_state(6, engine, game)

    assert state["status"] == "CHECK"
    assert "Teams verified" in state["reason"]
    assert "identity is unavailable" not in state["reason"]


def test_v39_compact_step_state_preserves_real_gates() -> None:
    page = importlib.import_module("cfb_over_under_clean_page_v39")
    game = {"away_team": "Syracuse", "home_team": "Pittsburgh", "away_espn_id": "183", "home_espn_id": "221"}
    engine = {"status": "GATED", "reason": "Required pace inputs are unavailable."}

    state = page._compact_step_state(4, engine, game)

    assert state["status"] == "GATED"
    assert "pace inputs" in state["reason"]


def test_v39_compact_renderer_contract() -> None:
    page = importlib.import_module("cfb_over_under_clean_page_v39")
    game = {
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "away_espn_id": "183",
        "home_espn_id": "221",
        "venue": "Acrisure Stadium",
        "broadcast": "ESPN",
    }
    away = {"record": {"wins": 1, "losses": 1}}
    home = {"record": {"wins": 2, "losses": 0}}
    result = {
        "pace_engine": {"status": "READY", "reason": "Pace evidence ready."},
        "explosive_engine": {"status": "GATED", "reason": "NCAA FBS/FCS identity is unavailable for one or both teams."},
        "red_zone_engine": {"status": "GATED", "reason": "NCAA FBS/FCS identity is unavailable for one or both teams."},
        "third_down_engine": {"status": "GATED", "reason": "NCAA FBS/FCS identity is unavailable for one or both teams."},
        "turnover_engine": {"status": "GATED", "reason": "NCAA FBS/FCS identity is unavailable for one or both teams."},
        "environment_engine": {"status": "READY", "reason": "Weather evidence ready."},
        "history_engine": {"status": "LIMITED", "reason": "Small sample."},
    }

    foundation = page._compact_foundation_html(game, away, home, result)
    steps = page._compact_steps_html(game, result)

    assert "MATCHUP FOUNDATION" in foundation
    assert "Syracuse" in foundation and "Pittsburgh" in foundation
    assert "1-1" in foundation and "2-0" in foundation
    assert "183" in foundation and "221" in foundation
    assert "WHAT MOVES THE TOTAL" in steps
    assert "Teams verified" in steps
    assert "identity is unavailable" not in steps
    assert "SPORTSBOOK 0.0%" in steps


def test_v39_remains_presentation_only() -> None:
    page = importlib.import_module("cfb_over_under_clean_page_v39")
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v38"
